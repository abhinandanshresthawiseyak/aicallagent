# # import datetime
# import json
# from airflow import DAG
# from airflow.operators.empty import EmptyOperator
# from airflow.decorators import task
# from time import sleep
# from airflow.providers.postgres.hooks.postgres import PostgresHook
# from datetime import datetime as dt
# from airflow.utils.trigger_rule import TriggerRule
# from airflow.sensors.time_delta import TimeDeltaSensor
# from datetime import datetime, timedelta
# import requests
# from airflow.models import TaskInstance

# with DAG(
#     dag_id="mydag",
#     start_date=datetime(2024, 12, 9),
#     schedule_interval=None,
#     is_paused_upon_creation=False,  # Force the DAG to be unpaused upon creation
# ):
    
#     start = EmptyOperator(task_id="start") # To make DAG more readable

#     @task(task_id='make_api_call')
#     def make_api_call():
#         # api_endpoint = "http://192.168.89.109:8001/call"
#         api_endpoint = f"http://192.168.79.109:8001/call"
#         data = {"number": 9868205040, "extension": 105}
#         response = requests.post(api_endpoint, data=data)
#         print(f"API call to {api_endpoint} completed with status code {response.status_code}")
#         return response.status_code

#     @task(task_id='update_flag')
#     def update_flag():
#         for _ in range(1000):
#             pass
#         print('updated')

#     # If we find caller_id in call_logs table, it means, the call is answered --> Now, we have to find out if proper interaction is done by the user
#     # If we don't find caller_id in call_logs table, it means, the call is unanswered --> Now, we'll find reason for unanswering like switch_off, busy, full_ring
#     @task(task_id='check_if_callerid_is_present_in_calllogs_table')
#     def check_if_callerid_is_present_in_calllogs_table(caller_id):
#         hook = PostgresHook(postgres_conn_id='aicallagent')
#         sql = f'''
#             SELECT 
#                 *
#             FROM call_logs
#             WHERE caller_id = '{caller_id}'
#             limit 1;
#         '''
#         rows = hook.get_records(sql)

#         # If rows are not empty, the call is answered
#         if rows:
#             return 'answered'
#         else:
#             return 'unanswered'

#     # This task is for branching the if-else condition based on the caller_status is answered or unanswered which will be forward to the task based on answered/unansered,
#     # If answered --> go to  find_if_proper_interaction_is_completed task
#     # If unanswered --> go to find_reason_for_unanswered taskk
#     @task.branch(task_id='branch_on_call_status') # Similar to BranchPythonOperator
#     def branch_on_call_status(caller_status):
#         # Return the task that should run based on the caller status
#         if caller_status == 'unanswered':
#             return 'find_reason_for_unanswered'
#         else:
#             return 'find_if_proper_interaction_is_completed'

#     @task(task_id='find_reason_for_unanswered')
#     def find_reason_for_unanswered(channel_id=None):

#         status = {
#                 "User busy":"busy",
#                 "Normal Clearing": "switch_off",
#                 "Unknown":"full_ring"
#         }

#         channel_id = "9863800249986380024998638002499863800249"
#         with open(f"/opt/airflow/websocket-logs/{str(dt.today().date())}/{channel_id}.txt", 'r') as f:
#             file = f.read()

#         # with open(f"/opt/airflow/websocket-logs/2024-12-09/{channel_id}.txt", 'r') as f:
#         #     file = f.read()

#         # Assuming 'file' contains the JSON logs (as you read it from the file earlier)
#         logs = file.splitlines()

#         # Iterate over each log entry and check for 'cause_txt'
#         for log in logs:
#             log_data = json.loads(log)  # Parse the JSON string
#             cause_txt = log_data.get('cause_txt')
            
#             # If 'cause_txt' exists, print the cause and its value
#             if cause_txt:
#                 print(f"cause_txt: {status[cause_txt]}")


#     @task(task_id='find_if_proper_interaction_is_completed')
#     def find_if_proper_interaction_is_completed():
#         print("Interaction Complete")

#     # A dummy operator to make sure DAG looks clean and readable
#     end = EmptyOperator(task_id="end", trigger_rule=TriggerRule.ONE_SUCCESS)

#     # Task sequence
#     # Register the post_execute hook for update_flag task
#     update_flag_task = update_flag()
#     # update_flag_task.post_execute = post_execute
#     # pause_task = ()
#     check_caller_task = check_if_callerid_is_present_in_calllogs_table(caller_id='demo-scheduled-from-ui-nabil2a793628-94af-4864-b135-f9341212e0d2')
#     branch_task = branch_on_call_status(check_caller_task)
#     find_reason_for_unanswered_task = find_reason_for_unanswered()
#     complete_interaction_task = find_if_proper_interaction_is_completed()

#     # Set dependencies
#     start >> update_flag_task >> check_caller_task
#     check_caller_task >> branch_task
#     branch_task >> find_reason_for_unanswered_task
#     branch_task >> complete_interaction_task
#     find_reason_for_unanswered_task >> end
#     complete_interaction_task >> end

