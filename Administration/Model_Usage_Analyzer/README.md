# Azure OpenAI Completion Token Estimator

This tool estimates the expected number of completion (output) tokens per Azure OpenAI model request, based on 30 days of historical usage metrics. It uses Azure Monitor metrics to fetch daily totals of model requests and output tokens, computes per-request averages, and recommends an estimate that accounts for outliers.

## Features
- Queries **ModelRequests** and **OutputTokens** metrics daily over the last 30 days
- Calculates per-day output tokens per request safely (avoiding divide-by-zero)
- Computes overall and daily statistics: average, min, max, standard deviation, 95th and 99th percentiles
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

Sample output:
```
Estimated completion tokens per request:
recommended_tokens:  290.00
overall_avg     :  212.34
daily_avg       :  215.67
daily_min       :  150.00
daily_max       :  350.00
daily_std       :   45.12
daily_p95       :  290.00
daily_p99       :  340.00
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
- **95th percentile (p95)** = 95th percentile of this series ≈ **290**

The tool recommends **290** tokens per request as a conservative estimate, accounting for outliers.

---