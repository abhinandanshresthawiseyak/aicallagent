import uuid
from airflow import DAG
from airflow.operators.dummy import DummyOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from datetime import datetime, timedelta
import requests
from airflow.decorators import task
from airflow.utils import timezone
from airflow.utils.email import send_email
import os, json
from datetime import datetime as dt
from airflow.utils.trigger_rule import TriggerRule
from time import sleep
from airflow.operators.empty import EmptyOperator
from airflow.sensors.time_delta import TimeDeltaSensor

# Define a task failure callback function that will send email alerts incase of pipeline failure
def task_failure_alert(context):
    task_instance = context.get("task_instance")
    dag_id = context.get("dag").dag_id
    task_id = task_instance.task_id
    execution_date = context.get("execution_date")
    log_url = context.get("task_instance").log_url
    try_number = task_instance.try_number
    max_tries = task_instance.max_tries
    state = task_instance.state
    owner = task_instance.task.owner if hasattr(task_instance.task, 'owner') else "Unknown"
    start_date = task_instance.start_date
    end_date = task_instance.end_date
    duration = (end_date - start_date).total_seconds() if start_date and end_date else "N/A"
    exception = task_instance.xcom_pull(task_ids=task_id, key="exception", include_prior_dates=True)


    subject = f"Task Failed: {dag_id}.{task_id}"
    html_content = f"""
    <html>
        <body>
            <h2>Task Failure Alert</h2>
            <p><strong>Task ID:</strong> {task_id}</p>
            <p><strong>DAG ID:</strong> {dag_id}</p>
            <p><strong>Owner:</strong> {owner}</p>
            <p><strong>Execution Date:</strong> {execution_date}</p>
            <p><strong>Start Time:</strong> {start_date}</p>
            <p><strong>End Time:</strong> {end_date}</p>
            <p><strong>Duration:</strong> {duration} seconds</p>
            <p><strong>Current State:</strong> {state}</p>
            <p><strong>Attempt:</strong> {try_number} of {max_tries}</p>
            <p><strong>Error Message:</strong> {exception if exception else "No exception found"}</p>
            <p><strong>Logs:</strong> <a href="{log_url}" target="_blank">View Logs</a></p>
        </body>
    </html>
    """

    send_email(to="abhinandan.shrestha@wiseyak.com", subject=subject, html_content=html_content)

dag_config = {}

hook = PostgresHook(postgres_conn_id='aicallagent')
records = hook.get_records("""
    SELECT 
        id, caller_id, name, phone_number, scheduled_for_utc, assigned_container
    FROM user_details
    WHERE status = 'tts_saved_to_location'
""")

for record in records:
    id, caller_id, name, phone_number, scheduled_for_utc, assigned_container = record
    extension = assigned_container.split('-')[-1]
    dag_id = f"call_{phone_number}_{scheduled_for_utc.strftime('%Y-%m-%dT%H:%M:%S.%fZ%Z').replace('.','-').replace(':','-')}"
    
    dag_config[dag_id] = {'phone_number': phone_number, 'extension': extension, 'caller_id':caller_id, 'channelId':caller_id}

    with DAG(
        dag_id=dag_id,
        start_date=scheduled_for_utc,
        schedule_interval='@once',
        tags=["dynamic_api_call"],
        is_paused_upon_creation=False,  
        default_args={
            "on_failure_callback": task_failure_alert  
        },
    ) as dynamic_dag:

        start = DummyOperator(task_id='start')

        @task(task_id='make_api_call')
        def make_api_call(dag_id):
            config = dag_config[dag_id]
            api_endpoint = f"http://192.168.79.109:8001/call"
            data = {"number": config['phone_number'], "extension": config['extension'],"channelId": config['channelId']}
            response = requests.post(api_endpoint, data=data)
            print(f"API call to {api_endpoint} completed with status code {response.status_code}\nchannelId: {config['channelId']}")
            return response.status_code

        @task(task_id='wait_until_call')
        def wait_until_call(user_id):
            print(user_id)
            # hook = PostgresHook(postgres_conn_id='aicallagent')
            # sql = f"UPDATE user_details SET status = 'called', modified_on_utc = now() at time zone 'utc' WHERE id = {user_id}"
            # hook.run(sql)
            # print(f"Marked record {user_id} as scheduled.")
            sleep(60)

        # New task to wait for call completion
        # wait_for_call_completion = TimeDeltaSensor(
        #     task_id='wait_for_call_completion',
        #     delta=timedelta(minutes=5),  # Set the delay to 5 minutes
        #     poke_interval=60,  # Check every 60 seconds for the time delta
        #     timeout=600,  # Max wait time, i.e., 10 minutes
        # )
    
        @task(task_id='check_if_callerid_is_present_in_calllogs_table')
        def check_if_callerid_is_present_in_calllogs_table(dag_id):
            config = dag_config[dag_id]
            caller_id=config['caller_id']
            hook = PostgresHook(postgres_conn_id='aicallagent')
            sql = f"SELECT * FROM call_logs WHERE caller_id = '{caller_id}' limit 1;"
            rows = hook.get_records(sql)
            if rows:
                return 'answered'
            else:
                return 'unanswered'

        @task.branch(task_id='branch_on_call_status')
        def branch_on_call_status(caller_status):
            if caller_status == 'unanswered':
                return 'find_reason_for_unanswered'
            else:
                return 'find_if_proper_interaction_is_completed'

        @task(task_id='find_reason_for_unanswered')
        def find_reason_for_unanswered(dag_id):
            # Mapping for cause_txt and their meaning
            status = {
                "User busy": "busy",
                "Normal Clearing": "switch_off",
                "Unknown": "full_ring"
            }

            config = dag_config[dag_id]
            channelId=config['channelId'] # extract channelId from dag_config
            print(channelId)
            with open(f"/opt/airflow/websocket-logs/{str(dt.today().date())}/{channelId}.txt", 'r') as f:
                file = f.read()

            logs = file.splitlines()
            for log in logs:
                log_data = json.loads(log)
                cause_txt = log_data.get('cause_txt') # find cause_txt
                if cause_txt:
                    print(f"cause_txt: {status[cause_txt]}")

            hook = PostgresHook(postgres_conn_id='aicallagent')
            caller_id=config['caller_id']
            sql = f"UPDATE user_details SET status = '{status[cause_txt]}', modified_on_utc = now() at time zone 'utc' WHERE caller_id = '{caller_id}'"
            hook.run(sql)
            print(f"Marked record {caller_id} as {status[cause_txt]}.")

        @task(task_id='find_if_proper_interaction_is_completed')
        def find_if_proper_interaction_is_completed(dag_id):
            hook = PostgresHook(postgres_conn_id='aicallagent')
            caller_id=dag_config[dag_id]['caller_id']
            sql = f"UPDATE user_details SET status = 'answered', modified_on_utc = now() at time zone 'utc' WHERE caller_id = '{caller_id}'"
            hook.run(sql)
            print(f"Marked record {caller_id} as answered.")

        end = EmptyOperator(task_id="end", trigger_rule=TriggerRule.ONE_SUCCESS)

        # Task dependencies
        make_api_call_task = make_api_call(dag_id)
        wait_until_call_task = wait_until_call(id)
        # wait_for_call_completion_task = pause()
        check_caller_task = check_if_callerid_is_present_in_calllogs_table(dag_id)
        branch_task = branch_on_call_status(check_caller_task)
        find_reason_for_unanswered_task = find_reason_for_unanswered(dag_id)
        complete_interaction_task = find_if_proper_interaction_is_completed(dag_id)

        # start >> make_api_call_task >> update_schedule_flag_task >> wait_for_call_completion_task
        # wait_for_call_completion_task >> check_caller_task
        start >> make_api_call_task >> wait_until_call_task >> check_caller_task >> branch_task
        branch_task >> find_reason_for_unanswered_task
        branch_task >> complete_interaction_task
        find_reason_for_unanswered_task >> end
        complete_interaction_task >> end

        globals()[dag_id] = dynamic_dag
