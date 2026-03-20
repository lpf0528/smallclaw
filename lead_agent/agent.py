
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig


from dotenv import load_dotenv

load_dotenv()
model = ChatOpenAI(
    model="gpt-4o-mini",
    base_url='https://ai.keep.fm/v1/',
    temperature=0.1,
    max_tokens=1000,
    timeout=30
    # ... (other params)
)


# Define the graph
def make_lead_agent(config: RunnableConfig):
    return create_agent(
        model=model
    )
