from pydantic import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Antigravity Scraper"
    DEBUG: bool = True
    OUTPUT_DIR: str = "datasets"
    
    # Stealth Settings
    HEADLESS: bool = True
    MIN_DELAY: float = 1.0
    MAX_DELAY: float = 3.0
    
    # Image Settings
    MIN_WIDTH: int = 100
    MIN_HEIGHT: int = 100
    TARGET_SIZE: tuple = (512, 512)
    
    # Concurrency
    MAX_PARALLEL_DOWNLOADS: int = 10

    class Config:
        env_file = ".env"

settings = Settings()
