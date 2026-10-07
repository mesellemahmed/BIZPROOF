def test_xlsx_export(self):
    response = self.get(params={"export": "xlsx"})
    self.assertEqual(response.status_code, 200)
    workbook_data = response.getvalue()
    worksheet = load_workbook(filename=BytesIO(workbook_data))["Sheet1"]
    cell_array = [[cell.value for cell in row] for row in worksheet.rows]
    self.assertEqual(
        cell_array,
        [
            ["Search term(s)", "Views"],
            ["a query with three hits", 3],
            ["a query with two hits", 2],
            ["a query with one hit", 1],
        ],
    )
