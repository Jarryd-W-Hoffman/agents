from logging_helper import log_event


class WarehouseRepository:
    def find_by_id(self, id):
        log_event("warehouse.lookup", id=id)
        return {"id": id}
