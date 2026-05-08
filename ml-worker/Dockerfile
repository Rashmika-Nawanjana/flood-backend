FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir pandas numpy scikit-learn xgboost

COPY . .

CMD ["python", "ml-worker/worker.py"]