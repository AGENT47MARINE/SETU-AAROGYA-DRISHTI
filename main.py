import asyncio
import os
from services.nlp.processor_service import NLPProcessorService

async def main():
    print("--- SETU AAROGYA DRISHTI: PHASE 1 STARTUP ---")
    
    # Initialize service
    service = NLPProcessorService()
    
    # Run the processor
    try:
        await service.run()
    except KeyboardInterrupt:
        print("Service stopped by user.")
    except Exception as e:
        print(f"Service error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
