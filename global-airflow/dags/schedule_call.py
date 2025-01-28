# from airflow import DAG
# from airflow.operators.dummy import DummyOperator
# from airflow.providers.postgres.hooks.postgres import PostgresHook
# from datetime import datetime, timedelta
# import requests
# from airflow.decorators import task
# from airflow.utils import timezone
# from airflow.utils.email import send_email
# import os

# # Define a task failure callback function that will send email alerts incase of pipeline failure
# def task_failure_alert(context):
#     task_instance = context.get("task_instance")
#     dag_id = context.get("dag").dag_id
#     task_id = task_instance.task_id
#     execution_date = context.get("execution_date")
#     log_url = context.get("task_instance").log_url
#     try_number = task_instance.try_number
#     max_tries = task_instance.max_tries
#     state = task_instance.state
#     owner = task_instance.task.owner if hasattr(task_instance.task, 'owner') else "Unknown"
#     start_date = task_instance.start_date
#     end_date = task_instance.end_date
#     duration = (end_date - start_date).total_seconds() if start_date and end_date else "N/A"
#     exception = task_instance.xcom_pull(task_ids=task_id, key="exception", include_prior_dates=True)


#     subject = f"Task Failed: {dag_id}.{task_id}"
#     html_content = f"""
#     <html>
#         <body>
#             <h2>Task Failure Alert</h2>
#             <p><strong>Task ID:</strong> {task_id}</p>
#             <p><strong>DAG ID:</strong> {dag_id}</p>
#             <p><strong>Owner:</strong> {owner}</p>
#             <p><strong>Execution Date:</strong> {execution_date}</p>
#             <p><strong>Start Time:</strong> {start_date}</p>
#             <p><strong>End Time:</strong> {end_date}</p>
#             <p><strong>Duration:</strong> {duration} seconds</p>
#             <p><strong>Current State:</strong> {state}</p>
#             <p><strong>Attempt:</strong> {try_number} of {max_tries}</p>
#             <p><strong>Error Message:</strong> {exception if exception else "No exception found"}</p>
#             <p><strong>Logs:</strong> <a href="{log_url}" target="_blank">View Logs</a></p>
#         </body>
#     </html>
#     """

#     send_email(to="abhinandan.shrestha@wiseyak.com", subject=subject, html_content=html_content)


# # Prepare a dictionary to store phone_number and extension by dag_id
# dag_config = {}

# hook = PostgresHook(postgres_conn_id='aicallagent')
# records = hook.get_records("""
#     SELECT 
#         id, name, phone_number, scheduled_for_utc, assigned_container
#     FROM user_details
#     WHERE status = 'tts_saved_to_location'
# """)

# for record in records:
#     id, name, phone_number, scheduled_for_utc, assigned_container = record
#     # extension = assigned_container.split('-')[-2]
#     extension = assigned_container.split('-')[-1]
#     dag_id = f"call_{phone_number}_{scheduled_for_utc.strftime('%Y-%m-%dT%H:%M:%S.%fZ%Z').replace('.','-').replace(':','-')}"
#     dag_config[dag_id] = {'phone_number': phone_number, 'extension': extension}

#     with DAG(
#         dag_id=dag_id,
#         start_date=scheduled_for_utc,
#         schedule_interval='@once',
#         # end_date=datetime(2025, 12, 12, 0, 0),
#         # schedule_interval='*/1 * * * *',
#         tags=["dynamic_api_call"],
#         is_paused_upon_creation=False,  # Force the DAG to be unpaused upon creation
#         default_args={
#             "on_failure_callback": task_failure_alert  # Callback for all tasks
#         },
#     ) as dynamic_dag:

#         start = DummyOperator(task_id='start')

#         @task(task_id='make_api_call')
#         def make_api_call(dag_id):
#             config = dag_config[dag_id]
#             # api_endpoint = "http://192.168.89.109:8001/call"
#             api_endpoint = f"http://192.168.79.109:8001/call"
#             data = {"number": config['phone_number'], "extension": config['extension']}
#             response = requests.post(api_endpoint, data=data)
#             print(f"API call to {api_endpoint} completed with status code {response.status_code}")
#             return response.status_code

#         @task(task_id='update_schedule_flag')
#         def update_schedule_flag(user_id):
#             hook = PostgresHook(postgres_conn_id='aicallagent')
#             sql = f"UPDATE user_details SET status = 'answered', modified_on_utc = now() at time zone 'utc' WHERE id = {user_id}"
#             hook.run(sql)
#             print(f"Marked record {user_id} as scheduled.")

#         end = DummyOperator(task_id='end')


#         # Define task dependencies
#         start >> make_api_call(dag_id) >> update_schedule_flag(id) >> end

#         globals()[dag_id] = dynamic_dag  # Add the DAG to the global namespace
