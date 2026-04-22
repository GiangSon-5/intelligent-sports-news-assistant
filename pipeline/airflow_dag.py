from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

# Default configuration for Tasks
default_args = {
    'owner': 'system_admin',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Initialize DAG
with DAG(
    'sports_news_pipeline',
    default_args=default_args,
    description='Automated Sports News Crawling and Reporting Pipeline',
    schedule_interval='0 6 * * *', # Runs automatically every day at 6:00 AM
    start_date=datetime(2026, 4, 20),
    catchup=False,
    tags=['sports', 'crawler', 'report'],
) as dag:

    # -------------------------------------------------------------------------
    # Tasks using BashOperator to call main.py directly
    # cwd=/opt/airflow/app parameter ensures code runs exactly as on Local
    # -------------------------------------------------------------------------

    crawl_task = BashOperator(
        task_id='step_crawl',
        bash_command='python main.py --step crawl',
        cwd='/opt/airflow/app',
    )

    process_task = BashOperator(
        task_id='step_process',
        bash_command='python main.py --step process',
        cwd='/opt/airflow/app',
    )

    analyze_task = BashOperator(
        task_id='step_analyze',
        bash_command='python main.py --step analyze',
        cwd='/opt/airflow/app',
    )

    report_task = BashOperator(
        task_id='step_report',
        bash_command='python main.py --step report',
        cwd='/opt/airflow/app',
    )

    # -------------------------------------------------------------------------
    # Set up Workflow (Linear execution order)
    # -------------------------------------------------------------------------
    crawl_task >> process_task >> analyze_task >> report_task
