import requests
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any


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
            'name': name,
            'desc': desc
            # 'desc': desc
        })
        if due:
            query['due'] = due

        response = requests.post(url, params=query)
        if response.status_code == 200:
            card = response.json()
            print(f"✅ Card created: {card['name']}")
            print(f"   URL: {card['url']}")
            return card
        else:
            print(f"❌ Error: {response.status_code}")
            return None

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