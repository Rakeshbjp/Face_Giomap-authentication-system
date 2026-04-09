import asyncio
import httpx

async def test_auth():
    base_url = "https://face-auth-backend-q40q.onrender.com/api/auth"
    
    # Try testing the face login or password login
    print("Testing health...")
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{base_url}/health")
        print("Health:", res.text)
        
        # We need a user to test. Let's do a dummy login to see what error getProfile gives
        # Or I can test locally hitting my local uvicorn since Render could be slow.
        # But wait, Render is live and has the db.

if __name__ == "__main__":
    asyncio.run(test_auth())
