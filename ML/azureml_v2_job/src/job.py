import time
from azure.ai.ml import MLClient
from azure.ai.ml.entities import Data
from azure.ai.ml.constants import AssetTypes
from azure.identity import DefaultAzureCredential
import mltable
from dotenv import load_dotenv

load_dotenv()

# set the version number of the data asset to the current UTC time
VERSION = "1" #time.strftime("%Y.%m.%d.%H%M%S", time.gmtime())

# connect to the AzureML workspace
# NOTE: subscription_id, resource_group, workspace were set in a previous snippet.
ml_client = MLClient.from_config(credential=DefaultAzureCredential(),)


# get the latest version of the data asset
# Note: the variable VERSION is set in the previous code
data_asset = ml_client.data.get(name="jsonl_data_blob", version=VERSION)

# the table from the data asset id
tbl = mltable.load(f"azureml:/{data_asset.id}")

# load into pandas
df = tbl.to_pandas_dataframe()
df.head()