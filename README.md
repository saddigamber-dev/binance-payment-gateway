# Binance Payment Gateway

> A production-level personal cryptocurrency payment gateway leveraging FastAPI, PostgreSQL, and Binance API.

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
## 💻 Integration Guide
> wantntcan integrate this gateway into your main websites or bots using either of the two professional methods below. Both methods ensure that payment verification happens securely on your backend, preventing client-side manipulation (like Burp Suite).
### Method 1: Direct API Integration (For Custom UIs)
If you want to build your own custom frontend and completely hide the fact that a 3rd party gateway is being used, you can fetch the API directly.
Below is an example of a secure integration using a **Python (Flask) Backend** and an **HTML/JS Frontend**.
#### 1. The Backend (app.py)
This script securely calls the Gateway and checks payment status.
```python
from flask import Flask, render_template, request, jsonify, session
import requests

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Configuration
BINANCE_GATEWAY_URL = "[https://binance.digamber.in](https://binance.digamber.in)"
USD_TO_INR = 98
CREDIT_RATE = 0.5

@app.route('/crypto-payment')
def crypto_payment():
    """Show payment page"""
    session['username'] = 'test_user'
    session['credits'] = 1000
    
    return render_template('crypto_payment.html',
                         usd_to_inr=USD_TO_INR,
                         credit_rate=CREDIT_RATE,
                         session=session)

@app.route('/api/create-order', methods=['POST'])
def create_order():
    """Create payment order via gateway"""
    try:
        data = request.get_json()
        amount = data.get('amount')
        
        allowed_amounts = [10, 20, 30, 50, 100]
        if amount not in allowed_amounts:
            return jsonify({'success': False, 'error': 'Invalid amount'}), 400
        
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        payload = {
            "amount": float(amount),
            "currency": "USDT",
            "network": "BSC"
        }
        
        response = requests.post(
            f"{BINANCE_GATEWAY_URL}/api/orders",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            order_data = response.json()
            order_id = order_data.get('id')
            credits = amount * USD_TO_INR * CREDIT_RATE
            
            # TODO: Save order_id and credits to your database as PENDING
            
            return jsonify({
                'success': True,
                'order_id': order_id,
                'qr_code': order_data.get('qr_code_base64'),
                'address': order_data.get('deposit_address'),
                'amount_crypto': order_data.get('unique_amount'),
                'credits': credits
            })
        else:
            return jsonify({'success': False, 'error': 'Gateway error'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/check-order/<order_id>', methods=['GET'])
def check_order(order_id):
    """Check payment status securely on the server"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        }
        
        response = requests.get(
            f"{BINANCE_GATEWAY_URL}/api/orders/{order_id}",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            order_data = response.json()
            status = order_data.get('status', 'PENDING')
            
            if status.upper() == 'CONFIRMED':
                # TODO: Update user credits in database (Delivery)
                pass
            
            return jsonify({
                'success': True,
                'status': status.lower(),
                'is_completed': status.upper() == 'CONFIRMED'
            })
        else:
            return jsonify({'success': True, 'status': 'pending'})
            
    except Exception as e:
        return jsonify({'success': True, 'status': 'pending'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)

```
#### 2. The Frontend (templates/crypto_payment.html)
This is a sleek, modern UI that interacts with your Flask backend.
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Crypto Payment Integration</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }
        .container { max-width: 500px; margin: 0 auto; }
        .card { background: white; border-radius: 20px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); overflow: hidden; }
        .header { background: linear-gradient(135deg, #f0b90b, #d4a00a); padding: 20px; text-align: center; }
        .header h1 { color: #000; font-size: 1.5rem; }
        .balance { background: #f8f9fa; padding: 15px; text-align: center; border-bottom: 1px solid #eee; }
        .balance span { font-weight: bold; color: #f0b90b; font-size: 1.2rem; }
        .section { padding: 20px; }
        .title { font-weight: bold; margin-bottom: 15px; color: #333; }
        .amount-buttons { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 20px; }
        .amount-btn { background: white; border: 2px solid #e0e0e0; border-radius: 12px; padding: 12px; cursor: pointer; transition: all 0.3s ease; text-align: center; }
        .amount-btn:hover { border-color: #f0b90b; background: #fff8e7; }
        .amount-btn.selected { border-color: #f0b90b; background: #f0b90b; }
        .price { font-size: 1.2rem; font-weight: bold; }
        .credits { font-size: 0.7rem; color: #666; }
        .amount-btn.selected .credits { color: #000; }
        .proceed-btn { width: 100%; padding: 14px; background: linear-gradient(135deg, #f0b90b, #d4a00a); border: none; border-radius: 12px; font-weight: bold; font-size: 1rem; cursor: pointer; transition: transform 0.2s; }
        .proceed-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .proceed-btn:not(:disabled):hover { transform: translateY(-2px); }
        .iframe-container { padding: 20px; background: white; }
        .payment-iframe { width: 100%; height: 550px; border: none; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
        .loading { text-align: center; padding: 40px; }
        .spinner { width: 50px; height: 50px; border: 4px solid #f3f3f3; border-top: 4px solid #f0b90b; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 15px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .back-btn { width: 100%; padding: 12px; background: #f0f0f0; border: none; border-radius: 12px; margin-top: 15px; cursor: pointer; }
        .hidden { display: none; }
        .note { font-size: 0.7rem; color: #888; text-align: center; padding: 15px; border-top: 1px solid #eee; }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="header">
                <h1>💰 Crypto Payment</h1>
                <p>Pay with USDT • BEP20 Network</p>
            </div>

            <div class="balance">
                💳 Your Balance: <span id="user-credits">{{ session.credits }}</span> Credits
            </div>

            <div id="step-select">
                <div class="section">
                    <div class="title">👇 Select Amount</div>
                    <div class="amount-buttons">
                        <button class="amount-btn" data-amount="10">
                            <div class="price">$10</div>
                            <div class="credits">≈ {{ (10 * usd_to_inr * credit_rate)|round(1) }} Credits</div>
                        </button>
                        <button class="amount-btn" data-amount="20">
                            <div class="price">$20</div>
                            <div class="credits">≈ {{ (20 * usd_to_inr * credit_rate)|round(1) }} Credits</div>
                        </button>
                    </div>
                    <button id="proceed-btn" class="proceed-btn" disabled>
                        ➡ Proceed to Payment
                    </button>
                </div>
            </div>

            <div id="step-loading" class="hidden">
                <div class="loading">
                    <div class="spinner"></div>
                    <p>Creating payment order...</p>
                </div>
            </div>

            <div id="step-payment" class="hidden">
                <div class="iframe-container">
                    <iframe id="payment-iframe" class="payment-iframe" src=""></iframe>
                    <button id="back-btn" class="back-btn">← Back to Amount Selection</button>
                </div>
            </div>

            <div class="note">
                🔒 Secure payment • Credits added automatically after confirmation
            </div>
        </div>
    </div>

    <script>
        let selectedAmount = null;
        let currentOrderId = null;
        let checkInterval = null;

        document.querySelectorAll('.amount-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                document.querySelectorAll('.amount-btn').forEach(b => b.classList.remove('selected'));
                this.classList.add('selected');
                selectedAmount = this.dataset.amount;
                document.getElementById('proceed-btn').disabled = false;
            });
        });

        document.getElementById('proceed-btn').addEventListener('click', async () => {
            if (!selectedAmount) return;

            document.getElementById('step-select').classList.add('hidden');
            document.getElementById('step-loading').classList.remove('hidden');

            try {
                const response = await fetch('/api/create-order', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ amount: parseFloat(selectedAmount) })
                });

                const data = await response.json();

                if (data.success) {
                    currentOrderId = data.order_id;
                    const iframe = document.getElementById('payment-iframe');
                    iframe.src = `https://binance.digamber.in/?amount=${selectedAmount}&order_id=${currentOrderId}`;
                    
                    document.getElementById('step-loading').classList.add('hidden');
                    document.getElementById('step-payment').classList.remove('hidden');
                    
                    startPaymentCheck();
                } else {
                    throw new Error(data.error || 'Failed to create order');
                }
            } catch (error) {
                alert('Error: ' + error.message);
                document.getElementById('step-loading').classList.add('hidden');
                document.getElementById('step-select').classList.remove('hidden');
            }
        });

        function startPaymentCheck() {
            if (checkInterval) clearInterval(checkInterval);
            
            checkInterval = setInterval(async () => {
                try {
                    const response = await fetch(`/api/check-order/${currentOrderId}`);
                    const data = await response.json();
                    
                    if (data.is_completed) {
                        clearInterval(checkInterval);
                        alert('✅ Payment Successful! Credits added to your account.');
                        
                        const balanceSpan = document.getElementById('user-credits');
                        const currentBalance = parseInt(balanceSpan.innerText);
                        const earnedCredits = document.querySelector('.amount-btn.selected .credits').innerText.match(/\d+/)[0];
                        balanceSpan.innerText = currentBalance + parseInt(earnedCredits);
                        
                        setTimeout(() => { window.location.reload(); }, 2000);
                    }
                } catch (error) {
                    console.error('Status check error:', error);
                }
            }, 5000);
        }

        document.getElementById('back-btn').addEventListener('click', () => {
            if (checkInterval) clearInterval(checkInterval);
            document.getElementById('step-payment').classList.add('hidden');
            document.getElementById('step-select').classList.remove('hidden');
        });
    </script>
</body>
</html>

```
### Method 2: Discord / Telegram Bot Integration (100% Hacker-Proof)
**Best for:** Selling digital roles, VIP access, or game items directly inside a chat platform.
Because bots use Server-to-Server (S2S) communication, this method is completely immune to client-side manipulation (like Burp Suite). The user cannot fake a success response because the verification happens entirely on your backend.
**Example Flow (Python discord.py & aiohttp):**
 1. User types !buy_vip.
 2. Bot silently POSTs to your Gateway API to generate a unique payment.
 3. Bot displays the exact amount and address in the chat via an Embed.
 4. Bot checks the Gateway API every 10 seconds. Upon a CONFIRMED status, it securely delivers the digital good.
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
                    return
