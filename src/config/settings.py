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
                # 默认不内置任何 Cookie，认证信息由用户在界面中输入并保存在本地 config.json（不纳入版本控制）
                "cookie": "",
                "remember_auth": True
            },
            "ui": {
                # 界面主题：system（跟随系统）/ light（浅色）/ dark（深色）
                "theme": "system"
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