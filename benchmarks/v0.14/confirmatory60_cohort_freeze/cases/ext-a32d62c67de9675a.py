def _timesheet_convert_sol_uom(self, sol, to_unit):
    to_uom = self.env.ref(to_unit)
    return round(sol.product_uom_id._compute_quantity(sol.product_uom_qty, to_uom, raise_if_failure=False), 2)
