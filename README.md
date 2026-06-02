# Binance Payment Gateway

A production-level personal cryptocurrency payment gateway leveraging FastAPI, PostgreSQL, and Binance API.

## Features
- Strict 20-minute expiry windows with active background cleanup.
- Generates unique floating-point payments to track transactions to static Binance account addresses.
- Auto-extracts actual client IPs behind Cloudflare (`CF-Connecting-IP` / `X-Forwarded-For`).
- Strictly limits users to 1 active pending order per IP to prevent spam and DB bloat.
- Auto-confirms payments via Binance API polling and sends Telegram notifications.

## Environment Variables (.env)
This project is built to accept your exact existing variables.
```text
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
DATABASE_URL=postgres://user:pass@host/db
JWT_SECRET=your_secret
DEBUG=False
HOST=0.0.0.0
PORT=10000
```

💻 Integration Guide
You can integrate this gateway into your main websites using either of the two methods below.

Method 1: Easy Iframe Embed (Recommended for Quick Setup)
The simplest way to use the gateway. This embeds the full UI (including the amount input, QR code generator, and expiration animations) directly into your website.
Add this HTML snippet anywhere on your site:
```
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>My Simple Store</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #f4f7f6; text-align: center; padding: 50px; }
        .iframe-box { 
            max-width: 400px; 
            margin: 0 auto; 
            border: 4px solid #333; 
            border-radius: 15px; 
            overflow: hidden; 
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
    </style>
</head>
<body>

    <h1>Buy Premium Membership - $10</h1>
    <p>Complete your payment in the secure box below:</p>

    <div class="iframe-box">
        <iframe 
            src="https://binance.digamber.in/"
            width="100%" 
            height="550px" 
            style="border: none;">
        </iframe>
    </div>

</body>
</html>
```

Method 2: Direct API Integration (For Custom UIs)
If you want to build your own custom frontend and completely hide the fact that a 3rd party gateway is being used, you can fetch the API directly. CORS is fully enabled.
Use this JavaScript example in your frontend to generate a payment:
```
async function generateCustomCryptoPayment(cartTotal) {
    try {
        const response = await fetch('[https://binance.digamber.in/api/orders](https://binance.digamber.in/api/orders)', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                amount: cartTotal, 
                currency: "USDT", 
                network: "BSC" 
            })
        });

        const orderData = await response.json();

        if (response.ok) {
            console.log("Order Created Successfully:", orderData);
            
            // Map the data to your own custom HTML elements
            // document.getElementById('my-qr-image').src = orderData.qr_code_base64;
            // document.getElementById('my-address-text').innerText = orderData.deposit_address;
            // document.getElementById('my-exact-amount').innerText = orderData.unique_amount;
            
            alert(`Please pay exactly ${orderData.unique_amount} USDT`);
        } else {
            console.error("Gateway Error:", orderData.detail);
        }
    } catch (error) {
        console.error("Network error during payment generation:", error);
    }
}

// Call the function with the amount to charge
// generateCustomCryptoPayment(15);
```
### Method 3: Discord / Telegram Bot Integration (100% Hacker-Proof)
**Best for:** Selling digital roles, VIP access, or game items directly inside a chat platform. 

Because bots use Server-to-Server (S2S) communication, this method is completely immune to client-side manipulation (like Burp Suite). The user cannot fake a success response because the verification happens entirely on your backend.

**Example Flow (Python `discord.py` & `aiohttp`):**
1. User types `!buy_vip`.
2. Bot silently POSTs to your Gateway API to generate a unique payment.
3. Bot displays the exact amount and address in the chat via an Embed.
4. Bot checks the Gateway API every 10 seconds. Upon a `CONFIRMED` status, it delivers the digital good.

```python
import discord
from discord.ext import commands
import aiohttp
import asyncio

bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())
GATEWAY_URL = "[https://binance.digamber.in/api/orders](https://binance.digamber.in/api/orders)"

@bot.command()
async def buy_vip(ctx):
    await ctx.send("🔄 Generating secure invoice...")

    # 1. Generate Order Server-to-Server
    async with aiohttp.ClientSession() as session:
        payload = {"amount": 5.0, "currency": "USDT", "network": "BSC"}
        async with session.post(GATEWAY_URL, json=payload) as res:
            order = await res.json()
            
    order_id = order["id"]
    
    # 2. Display invoice to the user
    embed = discord.Embed(title="💎 VIP Access", color=discord.Color.gold())
    embed.add_field(name="Amount", value=f"**{order['unique_amount']} USDT (BEP20)**", inline=False)
    embed.add_field(name="Address", value=f"`{order['deposit_address']}`", inline=False)
    embed.set_footer(text=f"ID: {order_id} | Expires in 20 mins")
    await ctx.send(embed=embed)
    
    # 3. Securely poll for confirmation
    async with aiohttp.ClientSession() as session:
        for _ in range(120): # Check every 10 seconds for 20 minutes
            await asyncio.sleep(10)
            async with session.get(f"{GATEWAY_URL}/{order_id}") as check_res:
                status_data = await check_res.json()
                
                if status_data["status"] == "CONFIRMED":
                    await ctx.send(f"✅ Payment Success, {ctx.author.mention}! Your VIP role has been added.")
                    return
                elif status_data["status"] == "EXPIRED":
                    await ctx.send(f"⏳ {ctx.author.mention}, your order `{order_id}` has expired.")
                    API
