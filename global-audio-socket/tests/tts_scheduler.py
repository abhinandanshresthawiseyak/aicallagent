import pendulum
from airflow import DAG
from airflow.decorators import task
from airflow.models.dagrun import DagRun
from airflow.utils.state import State
from airflow.utils.session import provide_session
from airflow.utils.trigger_rule import TriggerRule
from airflow.operators.dummy import DummyOperator
from airflow.utils.email import send_email
from airflow.providers.postgres.hooks.postgres import PostgresHook
from datetime import datetime, timedelta
import requests

def task_failure_alert():
    pass

with DAG(
    dag_id="caller",
    schedule=None,
    start_date=pendulum.datetime(2024, 11, 18, tz="UTC"),
    catchup=False,
    default_args={
        "on_failure_callback": task_failure_alert  # Callback for all tasks
    },
    tags=["caller"],
) as dag:
    
    @task()  # Ensure it runs regardless of upstream task state i.e, even if print_hello or print_name fails, this task will run 
    def get_user_details():
        # Initialize the PostgresHook with the connection ID
        hook = PostgresHook(postgres_conn_id='aicallagent')

        sql='''
            SELECT
                *
            FROM user_details
            where status = 'pending'
        '''

        rows=hook.get_records(sql)
        return rows
       
    
    @task
    def create_dynamic_dags(records):
        """
        Create individual DAGs dynamically for each unscheduled record.
        """
        for record in records:
            id=record[0]
            phone_number=record[3]
            scheduled_for_utc = record[-2]
            extension = record[-3].split('-')[-1]
            # Convert call_timestamp to datetime object
            # call_time = scheduled_for_utc.strftime("%Y-%m-%d %H:%M:%S")

            print(id, scheduled_for_utc,extension,phone_number)

            # Create a unique DAG ID
            dag_id = f"dynamic_dag_{id}"

            # Define the default arguments for each DAG
            # Dynamically define the DAG
            with DAG(
                dag_id=dag_id,
                description=f'Dynamic DAG for API call {id}',
                schedule_interval=None,  # One-time execution
                start_date=scheduled_for_utc,
                catchup=False,
                tags=["dynamic_api_call"],
            ) as dynamic_dag:

                @task
                def make_api_call(api_endpoint: str):
                    """
                    Task to make the API call.
                    """
                    # Parameters to send in the query string
                    params = {
                        "number": phone_number,
                        "extension": extension
                    }

                    response = requests.post(api_endpoint, params=params)
                    print(f"API call to {api_endpoint} completed with status code {response.status_code}")
                    return response.status_code

                @task
                def update_schedule_flag(record_id: int):
                    """
                    Task to update the scheduled flag for the given record ID.
                    """
                    hook = PostgresHook(postgres_conn_id="aicallagent")
                    sql = f"UPDATE user_details SET status = 'scheduled' WHERE id = {id}"
                    hook.run(sql)
                    print(f"Marked record {record_id} as scheduled.")

                # Define the tasks using the @task decorator
                api_task = make_api_call(api_endpoint="http://192.168.89.109:8001/call")
                update_flag_task = update_schedule_flag(id)

                # Set task dependencies
                api_task >> update_flag_task

            # Add the dynamically created DAG to the global namespace for Airflow to discover it
            globals()[dag_id] = dynamic_dag

    get_records_task=get_user_details()
    call=create_dynamic_dags(get_records_task)

    get_records_task >> call
