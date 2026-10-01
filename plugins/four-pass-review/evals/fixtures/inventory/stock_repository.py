from logging_helper import log_event


class StockRepository:
    def find_by_sku(self, sku):
        log_event("stock.lookup", sku=sku)
        return {"sku": sku, "qty": 0}
