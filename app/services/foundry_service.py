import json
from datetime import datetime

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import ListSortOrder
from decouple import config

from app.kafka_producer import send_transaction
from app.schemas import StandardKafkaEvent
from .ticketing_trello_service import TrelloClient


card_counter = 0

class FoundryAnalytics:
    @staticmethod
    async def foundry_processing(data):
        project = AIProjectClient(credential=DefaultAzureCredential(), endpoint=config('ENDPOINT_FOUNDRY'))
        agent = project.agents.get_agent(config("AGENT"))
        thread = project.agents.threads.create()
        print(f"DATA FROM MODEL ANOMALY:\n{data}")
        print(f"Created thread, ID: {thread.id}")

        content = (f"I have JSON log data on anomaly detection, this is log data {data}. "
                   "'prediction': -1 means anomaly, 'prediction': 1 means normal. "
                   "Explain the causes of anomalies and normality based on this log data, "
                   "considering cross-channel factors such as location differences (city or longitude/latitude within a 1-hour period), "
                   "OTP errors or multiple OTP failures, ATM anomalies (unusual withdrawal location, frequency, or amount), "
                   "QRIS anomalies (suspicious merchants or abnormal frequency), "
                   "transfer anomalies (large amounts, high frequency, or new/blacklisted recipients), "
                   "and login anomalies (new device, IP, or unusual session patterns)")

        message = project.agents.messages.create(thread_id=thread.id,
                                                 role="user",
                                                 content=content)

        run = project.agents.runs.create_and_process(thread_id=thread.id,
                                                     agent_id=agent.id)

        if run.status == "failed":
            return {"status": "failed", "details": run.last_error}

        else:
            print(f"Run status: {run.status}")
            print("Messages in thread:")
            messages = project.agents.messages.list(thread_id=thread.id,
                                                    order=ListSortOrder.ASCENDING)

            assistant_messages = [text_msg.text.value
                                  for message in messages
                                  if message.role == "assistant" and message.text_messages
                                  for text_msg in message.text_messages]

            now = datetime.utcnow()
            success_event = StandardKafkaEvent(timestamp=now,
                                               log_type="foundry_response",
                                               processing_time_ms=int(datetime.utcnow().timestamp() * 1000) % 1000,
                                               aml_screening_result=json.dumps(data),
                                               sanction_screening_result=json.dumps(assistant_messages))
            event_data = success_event.model_dump(exclude_none=True)
            event_data['timestamp'] = success_event.timestamp.isoformat() + 'Z'
            global card_counter
            card_counter += 1
            list_id = config("TRELLO_LIST_ID")
            name = f"Card #{card_counter}"
            api_key = config("TRELLO_API_KEY")
            token = config("TRELLO_TOKEN")

            await send_transaction(event_data)
            TrelloClient(api_key, token).create_card(list_id=list_id, name=name, desc=str(assistant_messages))

            for message in messages:
                print(f"\n{message.role.upper()}:")

                if message.text_messages:
                    for text_msg in message.text_messages:
                        print(text_msg.text.value)

                else:
                    print(message.content)

            return {"status": run.status, "messages": messages}
