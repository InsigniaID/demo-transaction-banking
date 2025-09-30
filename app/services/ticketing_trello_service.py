import tempfile

import requests
from sqlalchemy.orm import Session
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from app.models import TrelloCardSequence, TrelloCardLog


class TrelloClient:
    def __init__(self, api_key: str, token: str):
        self.api_key = api_key
        self.token = token
        self.base_url = 'https://api.trello.com/1'
        self.auth_params = {
            'key': self.api_key,
            'token': self.token
        }

    def test_connection(self):
        url = f"{self.base_url}/members/me"
        response = requests.get(url, params=self.auth_params)
        if response.status_code == 200:
            user = response.json()
            print(f"✅ Connected as: {user['fullName']} (@{user['username']})")
            return True
        else:
            print(f"❌ Connection failed: {response.status_code}")
            return False

    def get_boards(self):
        url = f"{self.base_url}/members/me/boards"
        response = requests.get(url, params=self.auth_params)
        if response.status_code == 200:
            return response.json()
        return None

    def get_lists(self, board_id):
        url = f"{self.base_url}/boards/{board_id}/lists"
        response = requests.get(url, params=self.auth_params)
        if response.status_code == 200:
            return response.json()
        return None

    def create_card(self, list_id, name, desc, due=None):
        url = f"{self.base_url}/cards"
        query = self.auth_params.copy()
        query.update({
            'idList': list_id,
            'name': name
            # 'desc': desc
        })
        if due:
            query['due'] = due

        if len(desc) <= 16384:
            query["desc"] = desc
        else:
            query["desc"] = "📎 Full analysis attached as .txt (too long for Trello desc)."

        response = requests.post(url, params=query)
        if response.status_code == 200:
            card = response.json()
            print(f"✅ Card created: {card['name']}")
            print(f"   URL: {card['url']}")

            if len(desc) > 16384:
                self.add_attachment(card["id"], desc)

            return card
        else:
            print(f"❌ Error: {response.status_code}")
            return None

    def add_attachment(self, card_id, text_content):
        url = f"{self.base_url}/cards/{card_id}/attachments"
        query = self.auth_params.copy()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8") as tmp:
            tmp.write(text_content)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as f:
            files = {"file": (os.path.basename(tmp_path), f)}
            response = requests.post(url, params=query, files=files)

        os.remove(tmp_path)

        if response.status_code == 200:
            print("📎 Attachment uploaded successfully.")
        else:
            print(f"❌ Error uploading attachment: {response.status_code} - {response.text}")

    def add_checklist(self, card_id, checklist_name, items):
        url = f"{self.base_url}/checklists"
        query = self.auth_params.copy()
        query.update({
            'idCard': card_id,
            'name': checklist_name
        })

        response = requests.post(url, params=query)
        if response.status_code == 200:
            checklist = response.json()
            checklist_id = checklist['id']

            # Add items
            for item in items:
                item_url = f"{self.base_url}/checklists/{checklist_id}/checkItems"
                item_query = self.auth_params.copy()
                item_query['name'] = item
                requests.post(item_url, params=item_query)

            print(f"✅ Checklist added with {len(items)} items")
            return checklist
        return None

    def add_comment(self, card_id, text):
        url = f"{self.base_url}/cards/{card_id}/actions/comments"
        query = self.auth_params.copy()
        query['text'] = text

        response = requests.post(url, params=query)
        if response.status_code == 200:
            print(f"✅ Comment added")
            return response.json()
        return None

    def update_card(self, card_id, **kwargs):
        url = f"{self.base_url}/cards/{card_id}"
        query = self.auth_params.copy()
        query.update(kwargs)

        response = requests.put(url, params=query)
        if response.status_code == 200:
            print(f"✅ Card updated")
            return response.json()
        return None

    def delete_card(self, card_id):
        url = f"{self.base_url}/cards/{card_id}"
        response = requests.delete(url, params=self.auth_params)
        if response.status_code == 200:
            print(f"✅ Card deleted")
            return True
        return False


print("✅ TrelloClient class defined")


def get_next_card_number_and_log(db: Session, assistant_messages: str) -> int:
    seq = db.query(TrelloCardSequence).first()
    if not seq:
        seq = TrelloCardSequence(last_number=1)
        db.add(seq)
        db.commit()
        db.refresh(seq)
        next_number = seq.last_number
    else:
        seq.last_number += 1
        db.commit()
        db.refresh(seq)
        next_number = seq.last_number

    log = TrelloCardLog(
        card_number=next_number,
        assistant_messages=assistant_messages
    )
    db.add(log)
    db.commit()

    return next_number