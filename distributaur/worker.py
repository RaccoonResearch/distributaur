import json
import subprocess
import sys
import os
import ssl
import time
from celery import Celery
from redis import ConnectionPool, Redis

ssl._create_default_https_context = ssl._create_unverified_context

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../"))

from distributaur.utils import get_blender_path, get_redis_values, upload_outputs

redis_url = get_redis_values()
pool = ConnectionPool.from_url(redis_url)
redis_client = Redis(connection_pool=pool)

app = Celery("tasks", broker=redis_url, backend=redis_url)

@app.task
def notify_completion(callback_result):
    print("All tasks have been completed!")
    print(callback_result)

@app.task(name="render_object", acks_late=True, reject_on_worker_lost=True)
def render_object(
    job_id,  # Include job_id to link tasks to their job
    combination_index: int,
    combination: list,
    width: int,
    height: int,
    output_dir: str,
    hdri_path: str,
    start_frame: int = 0,
    end_frame: int = 65,
) -> None:
    task_id = render_object.request.id
    print(f"Starting task {task_id} in job {job_id} for combination {combination_index}")
    update_task_status(job_id, task_id, "IN_PROGRESS")

    timeout = 600  # 10 minutes in seconds
    rendering_timeout = 2700  # 45 minutes in seconds

    start_time = time.time()
    print(f"Task {task_id} starting.")

    while True:
        elapsed_time = time.time() - start_time
        if elapsed_time > timeout:
            update_task_status(task_id, "TIMEOUT")
            print(f"Task {task_id} timed out before starting rendering")
            return

        try:
            # json stringify the combination list
            combination = json.dumps(combination)

            # escape the combination string for CLI
            combination = "\"" + combination.replace('"', '\\"') + "\""

            print("output_dir is", output_dir)

            os.makedirs(output_dir, exist_ok=True)

            args = f"--width {width} --height {height} --combination_index {combination_index}"
            args += f" --output_dir {output_dir}"
            args += f" --hdri_path {hdri_path}"
            args += f" --start_frame {start_frame} --end_frame {end_frame}"
            args += f" --combination {combination}"

            print("Args: ", args)

            application_path = get_blender_path()

            # TODO: Factor out comand
            command = f"{application_path} --background --python simian/render.py -- {args}"
            print("Worker running: ", command)

            rendering_start_time = time.time()
            print(f"Task {task_id} executing rendering command.")
            subprocess.run(["bash", "-c", command], timeout=rendering_timeout, check=False)
            print(f"Task {task_id} completed rendering.")

            elapsed_rendering_time = time.time() - rendering_start_time
            if elapsed_rendering_time > rendering_timeout:
                update_task_status(task_id, "TIMEOUT")
                print(f"Task {task_id} timed out after {elapsed_rendering_time} seconds of rendering")
                return

            upload_outputs(output_dir)

            # remove all files in the output directory
            for file in os.listdir(output_dir):
                file_path = os.path.join(output_dir, file)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as e:
                    print(e)

            update_task_status(task_id, "COMPLETE")
            print(f"Task {task_id} completed successfully")
            return

        except subprocess.TimeoutExpired:
            update_task_status(task_id, "TIMEOUT")
            print(f"Task {task_id} timed out after {timeout} seconds")
            return

        except Exception as e:
            update_task_status(job_id, task_id, "FAILED")
            print(f"Task {task_id} failed with error: {str(e)}")
            return

def update_task_status(job_id, task_id, status):
    key = f"celery-task-meta-{task_id}"
    value = json.dumps({"status": status})
    redis_client.set(key, value)
    print(f"Updated status for task {task_id} in job {job_id} to {status}")

if __name__ == "__main__":
    print("Starting Celery worker...")
    app.start(argv=['celery', 'worker', '--loglevel=info'])
