"""
Configuration settings for the Quake Query tool.
"""
import os
import json
from typing import Dict, Any

class Settings:
    def __init__(self):
        self.config_file = "config.json"
        self.load_config()

    def load_config(self) -> None:
        """Load configuration from file or use defaults"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
        else:
            self._config = self.get_default_config()
            self.save_config()

    def save_config(self) -> None:
        """Save current configuration to file"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)

    def get_default_config(self) -> Dict[str, Any]:
        """Return default configuration settings"""
        return {
            "api": {
                "base_url": "https://quake.360.net/api/search/query_string/quake_service",
                "headers": {
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            },
            "auth": {
                "cookie": "cert_common=54637115-aa19-4283-8d28-2691652472ed; __guid=73887506.3648837521006753000.1734043019051.955; Q=u%3D360H2781949797%26n%3D%26le%3DAQpkAwDlZQD4WGDjpKRhL29g%26m%3DZGtlWGWOWGWOWGWOWGWOWGWOZGVl%26qid%3D2781949797%26im%3D1_t011655040b3ed000bf%26src%3Dpcw_quake%26t%3D1; __NS_Q=u%3D360H2781949797%26n%3D%26le%3DAQpkAwDlZQD4WGDjpKRhL29g%26m%3DZGtlWGWOWGWOWGWOWGWOWGWOZGVl%26qid%3D2781949797%26im%3D1_t011655040b3ed000bf%26src%3Dpcw_quake%26t%3D1; T=s%3Dcaf51438443df2055983e03da7647274%26t%3D1734043034%26lm%3D%26lf%3D2%26sk%3Db6e758cadad1b8a9abf7bd13ee503aea%26mt%3D1734043034%26rc%3D%26v%3D2.0%26a%3D1; __NS_T=s%3Dcaf51438443df2055983e03da7647274%26t%3D1734043034%26lm%3D%26lf%3D2%26sk%3Db6e758cadad1b8a9abf7bd13ee503aea%26mt%3D1734043034%26rc%3D%26v%3D2.0%26a%3D1; Qs_lvt_357693=1734043011%2C1734119809; Qs_pv_357693=3696815488251497500%2C3269681091794928600%2C3021322404701157000%2C1162270333609022200",
                "remember_auth": True
            },
            "query": {
                "default_size": 100,
                "max_size": 1000,
                "default_format": "JSON"
            },
            "device_info": {
                "device_type": "PC",
                "os": "Windows",
                "os_version": "10.0",
                "language": "zh_CN",
                "network": "3g",
                "browser_info": "Chrome（版本: 100.0.4896.60  内核: Blink）"
            },
            "export": {
                "fields": [
                    "domain",
                    "ip",
                    "port",
                    "service.name",
                    "location.country_cn",
                    "location.province_cn",
                    "location.city_cn"
                ]
            }
        }

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value"""
        try:
            parts = key.split('.')
            value = self._config
            for part in parts:
                value = value[part]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value"""
        parts = key.split('.')
        config = self._config
        for part in parts[:-1]:
            if part not in config:
                config[part] = {}
            config = config[part]
        config[parts[-1]] = value
        self.save_config()

# Global settings instance
settings = Settings() 