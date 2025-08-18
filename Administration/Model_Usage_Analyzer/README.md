# Azure OpenAI Completion Token Estimator

This tool estimates the expected number of completion (output) tokens per Azure OpenAI model request, based on 30 days of historical usage metrics. It uses Azure Monitor metrics to fetch totals of model requests and output tokens at 1-minute granularity, computes per-request averages, and recommends an estimate that accounts for outliers. It also provides a breakdown by model deployment.

## Features
- Queries **ModelRequests** and **GeneratedTokens** metrics over the last 30 days at 1-minute granularity
- Calculates per-interval output tokens per request safely (avoiding divide-by-zero)
- Computes overall and per-minute statistics: average, min, max, standard deviation, 95th and 99th percentiles
- Recommends the 95th percentile as the conservative estimate to avoid underestimation
- Supports a `--debug` flag for verbose logging

## Requirements
- Python 3.7+
- Azure credentials with **Monitor Reader** role on the Azure OpenAI resource
- Libraries: `azure-monitor-query`, `azure-identity`, `python-dotenv`, `pandas`, `numpy`

Install dependencies:
```bash
pip install azure-monitor-query azure-identity python-dotenv pandas numpy
```

## Setup
1. Create a `.env` file or export environment variables:
   ```bash
   export AZURE_SUBSCRIPTION_ID=<your-subscription-id>
   export AZURE_RESOURCE_GROUP_NAME=<your-resource-group>
   export AZURE_AOAI_RESOURCE_NAME=<your-aoai-account-name>
   ```
2. Ensure your service principal or user has **Monitor Reader** access on the Azure OpenAI account.

## Usage
```bash
# Run with default INFO logging
python azure_estimate_completion.py

# Run with DEBUG logging
python azure_estimate_completion.py --debug
```

Sample output (abbreviated):
```
Estimated completion tokens per request:
overall_avg     :  212.34
minute_avg       :  215.67
minute_min       :  150.00
minute_max       :  350.00
minute_std       :   45.12
minute_p95       :  290.00
minute_p99       :  340.00
```

## Example Calculation

Suppose we have 5 days of data:

| Day | ModelRequests | OutputTokens | TokensPerRequest |
|-----|---------------|--------------|------------------|
|  1  |           100 |        20000 |             200  |
|  2  |           120 |        24000 |             200  |
|  3  |            80 |        16000 |             200  |
|  4  |           150 |        45000 |             300  |
|  5  |            90 |        22500 |             250  |

- **Overall average** = (20000+24000+16000+45000+22500) / (100+120+80+150+90) = 127500 / 540 ≈ **236.11**
- **Daily TokensPerRequest** series = [200, 200, 200, 300, 250]
- **95th percentile (p95)** = 95th percentile of this series ≈ **300**


---

Breakdown by model deployment (sorted by request count):
- Deployment: gpt-4o-mini
    overall_avg  : 198.12
    minute_avg   : 205.01
    minute_min   : 120.00
    minute_max   : 320.00
    minute_std   :  38.22
    minute_p95   : 275.00
    minute_p99   : 315.00
- Deployment: text-embedding-3-large
    overall_avg  : 17.45
    minute_avg   :  9.21
    minute_min   :  0.00
    minute_max   : 30.00
    minute_std   :  6.01
    minute_p95   : 20.00
    minute_p99   : 28.00
