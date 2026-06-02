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
