"""Data Products — package intelligence into sellable data feeds."""

from datetime import datetime
import json


class DataProducts:
    """Generates structured data products from Qrow intelligence."""

    def __init__(self):
        self.products = {}

    def create_product(self, name: str, description: str) -> dict:
        product = {
            "name": name,
            "description": description,
            "created_at": datetime.utcnow().isoformat(),
            "snapshots": [],
        }
        self.products[name] = product
        return product

    def add_snapshot(self, product_name: str, data: dict):
        if product_name not in self.products:
            return {"error": "product not found"}
        snapshot = {
            "timestamp": datetime.utcnow().isoformat(),
            "data": data,
        }
        self.products[product_name]["snapshots"].append(snapshot)
        return snapshot

    def export_product(self, product_name: str, fmt: str = "json") -> str:
        if product_name not in self.products:
            return ""
        if fmt == "json":
            return json.dumps(self.products[product_name], indent=2)
        raise NotImplementedError(f"Export format '{fmt}' not yet implemented")

    def list_products(self) -> list:
        return list(self.products.keys())
