import os
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

print("Azure OpenAI API Base URL:", os.getenv("AZURE_OPENAI_API_BASE")
      )
client = OpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    base_url=os.getenv("AZURE_OPENAI_API_BASE"),
)

response = client.responses.create(   
  model="gpt-4.1", # Replace with your model deployment name
  tools=[{"type": "web_search_preview"}], 
  input="Please perform a web search on the latest trends in renewable energy"
)

print(response.output_text)