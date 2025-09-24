import json
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import ListSortOrder
from decouple import config


class FoundryAnalytics:
    @staticmethod
    async def foundry_processing(data):
        project = AIProjectClient(credential=DefaultAzureCredential(),
                                  endpoint=config('ENDPOINT_FOUNDRY'))
        agent = project.agents.get_agent(config("AGENT"))
        thread = project.agents.threads.create()
        print(f"DATA FROM MODEL ANOMALY:\n{data}")
        print(f"Created thread, ID: {thread.id}")

        content = (f"Saya memiliki data JSON anomaly transaction seperti ini {data}"
                   "'prediction': -1 ini artinya anomaly, 'prediction': 1 artinya normal"
                   "jelaskan penyebab anomaly dan normal sesuai data, dan jika anomaly"
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
