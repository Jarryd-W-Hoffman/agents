from logging_helper import log_event


class SupplierRepository:
    def find_by_code(self, code):
        log_event("supplier.lookup", code=code)
        return {"code": code}
