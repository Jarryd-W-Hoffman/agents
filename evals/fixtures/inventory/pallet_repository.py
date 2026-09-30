import logging


class PalletRepo:
    # EVAL: seeded defect (consistency) -- siblings are <Thing>Repository
    # EVAL: with find_by_* and log_event; this departs on all three.
    def get(self, id):
        logging.getLogger(__name__).info("pallet lookup %s", id)
        return {"id": id}
