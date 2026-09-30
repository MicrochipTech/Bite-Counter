#!/usr/bin/env python3
import os
import sys
import queue
import threading
from functools import partial
from types import SimpleNamespace
from pathlib import Path
import collections
import numpy as np

repo_root = None
for p in Path(__file__).resolve().parents:
    if (p / "hailo_apps" / "config" / "config_manager.py").exists():
        repo_root = p
        break

if repo_root is not None:
    sys.path.insert(0, str(repo_root))

from hailo_apps.python.core.tracker.byte_tracker import BYTETracker
from hailo_apps.python.core.common.hailo_inference import HailoInfer
from hailo_apps.python.core.common.toolbox import (
    InputContext,
    VisualizationSettings,
    init_input_source,
    get_labels,
    load_json_file,
    preprocess,
    visualize,
    FrameRateTracker,
    stop_after_timeout,
)
from hailo_apps.python.core.common.defines import (
    MAX_INPUT_QUEUE_SIZE,
    MAX_OUTPUT_QUEUE_SIZE,
)
from hailo_apps.python.core.common.parser import get_standalone_parser
from hailo_apps.python.core.common.hailo_logger import (
    get_logger,
    init_logging,
    level_from_args,
)
from hailo_apps.python.core.common.core import handle_and_resolve_args, resolve_hef_path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from meal_monitoring_post_process import meal_inference_result_handler
from meal_state import MealState
from dashboard_renderer import DashboardRenderer
from pose_utils import PoseExtractor
from gesture_classifier import GestureClassifier

APP_NAME = "meal_monitoring"
logger = get_logger(__name__)


def parse_args():
    parser = get_standalone_parser()
    parser.description = "Meal monitoring dashboard: detect food/utensils and classify eating gestures."

    parser.add_argument(
        "--labels", "-l", type=str, default=None,
        help="Path to class labels file. Defaults to COCO labels.",
    )
    parser.add_argument(
        "--dashboard-width", type=int, default=400,
        help="Width in pixels of the dashboard panel (default: 400).",
    )
    parser.add_argument(
        "--pose-model", type=str, default="yolov8s_pose",
        help="Pose estimation model name (default: yolov8s_pose).",
    )
    parser.add_argument(
        "--no-gesture", action="store_true",
        help="Disable gesture detection (single-model mode for higher FPS).",
    )
    parser.add_argument(
        "--imu-port", type=str, default=None,
        help="Serial port for IMU sensor (future use).",
    )

    args = parser.parse_args()
    return args


def run_inference_pipeline(
    net,
    labels,
    input_context: InputContext,
    visualization_settings: VisualizationSettings,
    dashboard_width: int = 400,
    show_fps: bool = False,
    time_to_run: int | None = None,
    pose_model: str | None = None,
) -> None:
    labels = get_labels(labels)
    app_dir = Path(__file__).resolve().parent
    config_path = app_dir / "config.json"
    config_data = load_json_file(str(config_path))

    stop_event = threading.Event()
    fps_tracker = FrameRateTracker() if show_fps else None

    tracker_config = config_data.get("visualization_params", {}).get("tracker", {})
    tracker = BYTETracker(SimpleNamespace(**tracker_config))

    meal_state = MealState(stale_timeout=3.0)
    dashboard_renderer = DashboardRenderer(width=dashboard_width)

    pose_extractor = None
    gesture_classifier = None
    pose_hailo = None
    pose_model_h, pose_model_w = 640, 640

    if pose_model is not None:
        pose_hef = resolve_hef_path(pose_model, "pose_estimation")
        if pose_hef is not None:
            logger.info(f"Loading pose model: {pose_hef}")
            pose_hailo = HailoInfer(pose_hef, input_context.batch_size, output_type="FLOAT32")
            pose_model_h, pose_model_w, _ = pose_hailo.get_input_shape()
            pose_extractor = PoseExtractor()
            gesture_classifier = GestureClassifier()
            meal_state.update_gesture("Resting", 0.5, source="camera")
        else:
            logger.warning("Could not resolve pose model, running without gesture detection.")

    input_queue = queue.Queue(MAX_INPUT_QUEUE_SIZE)
    output_queue = queue.Queue(MAX_OUTPUT_QUEUE_SIZE)

    post_process_callback_fn = partial(
        meal_inference_result_handler,
        labels=labels,
        config_data=config_data,
        tracker=tracker,
        meal_state=meal_state,
        dashboard_renderer=dashboard_renderer,
        pose_extractor=pose_extractor,
        gesture_classifier=gesture_classifier,
        pose_model_h=pose_model_h,
        pose_model_w=pose_model_w,
    )

    od_hailo = HailoInfer(net, input_context.batch_size)
    height, width, _ = od_hailo.get_input_shape()

    preprocess_thread = threading.Thread(
        target=preprocess,
        args=(input_context, input_queue, width, height, None, stop_event),
        name="preprocess-thread",
    )

    infer_thread = threading.Thread(
        target=infer,
        args=(od_hailo, pose_hailo, input_queue, output_queue, stop_event),
        name="infer-thread",
    )

    preprocess_thread.start()
    infer_thread.start()

    if show_fps:
        fps_tracker.start()

    if time_to_run is not None:
        timer_thread = threading.Thread(
            target=stop_after_timeout,
            args=(stop_event, time_to_run),
            name="timer-thread",
            daemon=True,
        )
        timer_thread.start()

    try:
        visualize(
            input_context,
            visualization_settings,
            output_queue,
            post_process_callback_fn,
            fps_tracker,
            stop_event,
        )
    finally:
        stop_event.set()
        preprocess_thread.join()
        infer_thread.join()

    if show_fps:
        logger.info(fps_tracker.frame_rate_summary())

    logger.success("Meal monitoring completed.")

    if visualization_settings.save_stream_output or input_context.has_images:
        logger.info(f"Saved outputs to '{visualization_settings.output_dir}'.")


def _extract_result(bindings):
    if len(bindings._output_names) == 1:
        return bindings.output().get_buffer()
    return {
        name: np.expand_dims(bindings.output(name).get_buffer(), axis=0)
        for name in bindings._output_names
    }


def infer(od_hailo, pose_hailo, input_queue, output_queue, stop_event):
    while True:
        next_batch = input_queue.get()
        if not next_batch:
            break

        if stop_event.is_set():
            continue

        input_batch, preprocessed_batch = next_batch

        od_result = [None]
        pose_result = [None]

        def od_callback(completion_info, bindings_list):
            if completion_info.exception:
                logger.error(f"OD inference error: {completion_info.exception}")
            else:
                od_result[0] = _extract_result(bindings_list[0])

        def pose_callback(completion_info, bindings_list):
            if completion_info.exception:
                logger.error(f"Pose inference error: {completion_info.exception}")
            else:
                pose_result[0] = _extract_result(bindings_list[0])

        od_job = od_hailo.run(preprocessed_batch, od_callback)
        od_job.wait(10000)

        if pose_hailo is not None:
            pose_job = pose_hailo.run(preprocessed_batch, pose_callback)
            pose_job.wait(10000)

        if od_result[0] is not None:
            if pose_result[0] is not None:
                output_queue.put((input_batch[0], od_result[0], pose_result[0]))
            else:
                output_queue.put((input_batch[0], od_result[0]))

    od_hailo.close()
    if pose_hailo is not None:
        pose_hailo.close()
    output_queue.put(None)


def main() -> None:
    args = parse_args()
    init_logging(level=level_from_args(args))
    handle_and_resolve_args(args, "object_detection")

    input_context = InputContext(
        input_src=args.input,
        batch_size=args.batch_size,
        resolution=args.camera_resolution,
        frame_rate=args.frame_rate,
        video_unpaced=args.video_unpaced,
    )

    input_context = init_input_source(input_context)

    visualization_settings = VisualizationSettings(
        output_dir=args.output_dir,
        save_stream_output=args.save_output,
        output_resolution=args.output_resolution,
        no_display=args.no_display,
    )

    run_inference_pipeline(
        net=args.hef_path,
        labels=args.labels,
        input_context=input_context,
        visualization_settings=visualization_settings,
        dashboard_width=args.dashboard_width,
        show_fps=args.show_fps,
        time_to_run=args.time_to_run,
        pose_model=None if args.no_gesture else args.pose_model,
    )


if __name__ == "__main__":
    main()
