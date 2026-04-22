# 🚀 Airflow MLOps Operations Guide (Runbook)

This document provides detailed instructions on how to launch, monitor, and operate the Sports News Pipeline system via Apache Airflow (Docker Compose).

---

## 1. Prerequisites
- **Docker Desktop** (or Docker Engine & Docker Compose) installed.
- At least **3-4GB of free RAM** (as Airflow loads many background services).
- `.env` file created from `.env.example` with valid API Keys (Gemini/OpenAI).

---

## 2. Initial Launch Steps (Init & Build)

In your terminal (Command Prompt / PowerShell / VSCode Terminal), navigate to the project directory and run the following commands sequentially:

### Step 2.1: Build Docker Image
Since the Docker Image is configured to install OS libraries for WeasyPrint, you must build the image first:
```bash
docker-compose build
```
*(This process may take 3-5 minutes depending on your internet speed).*

### Step 2.2: Initialize Airflow Database
Airflow needs a database (Postgres) to store metadata. Run the following command to set up the data tables:
```bash
docker-compose run --rm airflow-scheduler airflow db migrate
```
*(This command only needs to be run ONCE in the project's lifetime).*

### Step 2.3: Create Admin User for login
```bash
docker-compose run --rm airflow-scheduler airflow users create \
    --role Admin \
    --username admin \
    --password admin \
    --email admin@system.com \
    --firstname Admin \
    --lastname User
```
*(After this command, the web UI login credentials will be: username **admin**, password **admin**).*

---

## 3. Running the System & Monitoring (Daily Operations)

### Start the system
Start the Airflow cluster in background mode:
```bash
docker-compose up -d
```
Wait about 1-2 minutes for all services (Postgres, Webserver, Scheduler) to finish starting up.

### Login to Web UI
1. Open your web browser and go to: [http://localhost:8080](http://localhost:8080)
2. Log in with the account `admin` / `admin`.

### How to run the Pipeline (DAG)
1. In the main screen (DAGs), you will see a DAG named **`sports_news_pipeline`**.
2. **Activate DAG**: Toggle the switch to the left of the DAG name from `Off` to `On`. (The system is scheduled to run automatically at 6:00 AM every day).
3. **Trigger DAG manually (Immediate run)**: Click the **▶️ (Play)** button in the Actions column on the right -> Select `Trigger DAG`.
4. Click directly on the DAG name `sports_news_pipeline`, switch to the **Graph** or **Grid** tab to see the 4 steps in progress (Crawl -> Process -> Analyze -> Report).

*(The final PDF/Markdown results will still be generated and stored in the `./storage/reports/` directory as configured).*

### Stop the system
When no longer in use and you want to free up computer RAM:
```bash
docker-compose down
```
*(Airflow's metadata in Postgres may be reset, but news data in the `./storage` folder remains preserved).*

---

## 4. Troubleshooting

**Error 1: Airflow Webserver reports Unhealthy or cannot access localhost:8080**
- Solution: Sometimes the Webserver starts slowly. Wait another minute or check the logs with: `docker-compose logs -f airflow-webserver`

**Error 2: A task (e.g., step_crawl) is reported in red (Failed)**
- Solution: Click on the red task in the Graph interface -> Select **Log** to see detailed error info.
- Since the system uses `BashOperator`, the error log will be similar to when running `python main.py --step crawl` directly. Usually, this is due to an expired API Key or network connectivity issues.

**Error 3: Manual `python main.py` no longer works?**
- Solution: The system operates independently. After ensuring the environment has all libraries installed with `pip install -r requirements.txt`, running `python main.py` manually will not affect Airflow.

---

## 5. Full Cleanup (Specific to this Project)

If you want to completely remove the project resources to free up disk space **WITHOUT** affecting other Containers/Images on your machine, use the following commands. These commands are scoped only to the resources defined in this project's `docker-compose.yml`.

### 5.1 Stop and Remove Containers & Networks
This only removes the containers and networks created by this project:
```bash
docker-compose down
```

### 5.2 Clear Everything including Database (Volumes)
Use this if you want to wipe the Airflow Postgres database (Note: this does NOT delete news data in `./storage`):
```bash
docker-compose down -v
```

### 5.3 Complete System Wipe (Containers, Volumes, Images)
This is the most thorough cleanup, removing the built images for this project as well:
```bash
docker-compose down -v --rmi local
```

> [!IMPORTANT]
> **Safety Note:** These `docker-compose` commands are safe because they only target resources associated with this specific project folder.

