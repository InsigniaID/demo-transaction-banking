import json
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import ListSortOrder
from decouple import config

project = AIProjectClient(credential=DefaultAzureCredential(),
                          endpoint=config('ENDPOINT_FOUNDRY'))

agent = project.agents.get_agent(config("AGENT"))

thread = project.agents.threads.create()
print(f"Created thread, ID: {thread.id}")

data = {
    "transaction_id": "TX12345",
    "amount": 1500000,
    "currency": "IDR",
    "status": "PENDING",
    "customer_id": "CUST001"
}

content = ("Saya memiliki transaksi dengan ID TX12345 sebesar 1.500.000 IDR yang masih berstatus PENDING. "
           "Apa yang sebaiknya saya lakukan?")

message = project.agents.messages.create(thread_id=thread.id,
                                         role="user",
                                         content=content)

run = project.agents.runs.create_and_process(thread_id=thread.id,
                                             agent_id=agent.id)

if run.status == "failed":
    print(f"Run failed: {run.last_error}")

else:
    print(f"Run status: {run.status}")
    print("Messages in thread:")
    messages = project.agents.messages.list(thread_id=thread.id,
                                            order=ListSortOrder.ASCENDING)

    for message in messages:
        print(f"\n{message.role.upper()}:")

        if message.text_messages:
            for text_msg in message.text_messages:
                print(text_msg.text.value)

        else:
            print(message.content)
