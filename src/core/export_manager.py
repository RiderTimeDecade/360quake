"""
Export manager for the Quake Query tool.
"""
import json
import csv
from typing import Dict, Any, List
from datetime import datetime
from ..config.settings import settings
from ..utils.logger import logger

class ExportManager:
    def __init__(self):
        """Initialize export manager"""
        self.export_fields = settings.get('export.fields')

    def export_json(self, data: Dict[str, Any], file_path: str) -> None:
        """Export data to JSON file"""
        try:
            logger.info(f"Exporting JSON to {file_path}")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("JSON export successful")
        except Exception as e:
            logger.error(f"JSON export failed: {str(e)}")
            raise

    def export_csv(self, data: Dict[str, Any], file_path: str) -> None:
        """Export data to CSV file"""
        try:
            logger.info(f"Exporting CSV to {file_path}")
            if not data or 'data' not in data:
                logger.warning("No data to export")
                return

            results = data['data']
            if not results:
                logger.warning("Empty results set")
                return

            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(self.export_fields)

                for item in results:
                    row = self._extract_row_data(item)
                    writer.writerow(row)

            logger.info("CSV export successful")
        except Exception as e:
            logger.error(f"CSV export failed: {str(e)}")
            raise

    def _extract_row_data(self, item: Dict[str, Any]) -> List[str]:
        """Extract row data based on export fields"""
        row = []
        for field in self.export_fields:
            if '.' in field:
                value = self._get_nested_value(item, field.split('.'))
            else:
                value = item.get(field, '')
            row.append(str(value))
        return row

    def _get_nested_value(self, item: Dict[str, Any], parts: List[str]) -> Any:
        """Get nested dictionary value"""
        value = item
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part, '')
            else:
                return ''
        return value

    def generate_filename(self, format: str) -> str:
        """Generate default filename with timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"quake_results_{timestamp}.{format.lower()}" 