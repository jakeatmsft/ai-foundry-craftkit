import os
import time
import argparse
from azure.ai.ml import MLClient
from azure.ai.ml.entities import Data
from azure.ai.ml.constants import AssetTypes
from azure.identity import DefaultAzureCredential
import mltable
import os


def get_ml_client(args):
    # subscription_id = os.environ.get('subscription_id')
    # resource_group = os.environ.get('resource_group')
    # workspace = os.environ.get('workspace')
    # client = MLClient(DefaultAzureCredential(), subscription_id, resource_group, workspace)
    client = MLClient.from_config(DefaultAzureCredential())    
    return client


def main(args):
    #ml_client = get_ml_client(args)
    # set the version number of the data asset to the current UTC time
    VERSION = "1" #time.strftime("%Y.%m.%d.%H%M%S", time.gmtime())

    # connect to the AzureML workspace
    # NOTE: subscription_id, resource_group, workspace were set in a previous snippet.
    ml_client = get_ml_client(None)

    # get the latest version of the data asset
    # Note: the variable VERSION is set in the previous code
    data_asset = ml_client.data.get(name="jsonl_data_blob", version=VERSION)

    # the table from the data asset id
    tbl = mltable.load(f"azureml:/{data_asset.id}")

    # load into pandas
    df = tbl.to_pandas_dataframe()
    print(df.head())

    print(f"Data asset name: {data_asset.name}")

# run script
if __name__ == "__main__":
    # parse args

    # run main function
    main(None)