# Copyright (c) 2025, Frappe and contributors
# For license information, please see license.txt

import json

import frappe
import requests
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt
from frappe.utils.data import get_link_to_form
from requests.exceptions import HTTPError

from erpnext_shipping.erpnext_shipping.utils import show_error_alert

FEDEX_PROVIDER = "Fedex"
TEST_BASE_URL = "https://apis-sandbox.fedex.com/ship/v1/shipments"


class Fedex(Document):
	pass


class FedexUtils:
	def __init__(self):
		settings = frappe.get_doc("Fedex", "Test")
		self.api_key = settings.api_key
		self.api_secret = settings.api_secret
		self.enabled = settings.enabled

		if not self.enabled:
			frappe.throw(_("Please enable Fedex Integration"))

	def get_available_services(self, delivery_address, parcels: list[dict]):
		"""
		Fetch available shipping services for given delivery address and parcels.
		"""
		if not self.enabled or not self.api_key or not self.api_secret:
			print("FedEx API is not enabled or missing credentials.")
			return []

		to_country = delivery_address.get("country_code", "").upper()
		if not to_country:
			print("Delivery address is missing country code.")
			return []
		# payload = {
		# 		"requestedShipment": {
		# 			"shipper": {
		# 				"address": {
		# 					"postalCode": "38017",
		# 					"countryCode": "US"
		# 				}
		# 			},
		# 			"recipients": [
		#  				{
		# 					"address": {
		# 						"postalCode": "38127",
		# 						"countryCode": "US"
		# 					}
		# 				}
		# 			],
		# 			"packagingType": "YOUR_PACKAGING",
		# 			"requestedPackageLineItems": [
		# 				{
		# 					"weight": {
		# 						"units": "LB",
		# 						"value": 10
		# 					}
		# 				}
		# 			]
		# 		},
		# 		"carrierCodes": [
		# 			"FDXG"
		# 		]740561073
		# 	}
		payload = {
			"accountNumber": {"value": "740561073"},
			"requestedShipment": {
				"shipper": {"address": {"postalCode": 641020, "countryCode": "IN"}},
				"recipient": {"address": {"postalCode": 638752, "countryCode": "IN"}},
				"pickupType": "DROPOFF_AT_FEDEX_LOCATION",
				"rateRequestType": ["ACCOUNT", "LIST"],
				"requestedPackageLineItems": [{"weight": {"units": "KG", "value": 100}}],
			},
		}

		try:
			headers = {
				"Content-Type": "application/json",
				"X-locale": "en_US",
				"Authorization": f"Bearer {self.get_access_token()}",
			}

			response = requests.post(
				"https://apis-sandbox.fedex.com/rate/v1/rates/quotes",
				data=json.dumps(payload),
				headers=headers,
			)
			response.raise_for_status()
			response_data = response.json()

			if "errors" in response_data:
				error_message = response_data["errors"][0]["message"]
				raise Exception(f"FedEx API Error: {error_message}")

			available_services = []

			rate_reply_details = response_data.get("output", {}).get("rateReplyDetails", [])

			for service in rate_reply_details:
				available_service = self.get_service_dict(service)
				available_services.append(available_service)

			return available_services

		except requests.exceptions.RequestException as e:
			if e.response is not None:
				print(f"Response Content: {e.response.content.decode()}")
			print(f"HTTP Request failed: {e}")
		except Exception as e:
			print(f"Error: {e}")

		return []

	def get_access_token(self):
		"""
		Get an access token from the FedEx OAuth2 endpoint.
		"""
		oauth_url = "https://apis-sandbox.fedex.com/oauth/token"
		payload = {
			"grant_type": "client_credentials",
			"client_id": "l74b3e7812356b426a90be5a8d11845166",
			"client_secret": "c09406cc6c684bf596a151009c7d5572",
		}
		headers = {"Content-Type": "application/x-www-form-urlencoded"}
		try:
			response = requests.post(oauth_url, data=payload, headers=headers)
			response.raise_for_status()
			token_data = response.json()
			return token_data.get("access_token")
		except requests.exceptions.RequestException as e:
			print(f"Error fetching access token: {e}")
			return None

	def get_service_dict(self, service):
		available_service = frappe._dict()
		available_service.service_provider = "FedEx"
		available_service.carrier = "FedEx"
		available_service.service_name = service["serviceName"]
		available_service.total_price = service.get("ratedShipmentDetails", [{}])[0].get(
			"totalNetCharge", 0.0
		)
		available_service.currency = service.get("ratedShipmentDetails", [{}])[0].get("currency", "INR")
		available_service.service_id = service["serviceType"]
		available_service.is_preferred = 1
		return available_service
