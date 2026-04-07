import os
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

token_provider = get_bearer_token_provider(
    DefaultAzureCredential(),
    "https://cognitiveservices.azure.com/.default",
)
base_url = os.getenv("AZURE_OPENAI_API_BASE") or os.getenv("AZURE_OPENAI_ENDPOINT")

print("Azure OpenAI API Base URL:", base_url)
client = OpenAI(
    api_key=token_provider,
    base_url=base_url,
)

response = client.responses.create(   
  model="gpt-4.1", # Replace with your model deployment name
  tools=[{"type": "web_search_preview"}], 
  input="Please perform a web search on the latest trends in renewable energy"
)

print(response.output_text)
