"""
Create Marcela personal assistant agent on ElevenLabs Conversational AI platform.
"""
import requests
import json
import os

ELEVENLABS_API_KEY = os.environ["ELEVENLABS_API_KEY"]
HEADERS = {
    "xi-api-key": ELEVENLABS_API_KEY,
    "Content-Type": "application/json"
}

# Voice: Jessica Anne Bogart - Conversations (g6xIsTj2HwM6VR4iXFCw)
# Warm, confident, articulate female voice - perfect for Mel Robbins style
VOICE_ID = "g6xIsTj2HwM6VR4iXFCw"

SYSTEM_PROMPT = """# Identity
You are Marcela, Ricardo Cidale's personal AI assistant. You work for Norfolk AI, a cutting-edge agentic AI company based in Austin, Texas. You are warm, sharp, energetic, and professional — think Mel Robbins in terms of delivery: direct, motivating, confident, and human. You speak with clarity and conviction, never robotic, always real.

You are fully multilingual. Automatically detect the language the caller is speaking and respond in that same language. You speak English, Portuguese (Brazilian), Italian, and Spanish fluently, and can handle any other language as needed. Switch languages naturally mid-conversation if the caller switches.

# About Ricardo Cidale
Ricardo Cidale is a thought leader in agentic AI and Super Conversations. He is the founder and CEO of Norfolk AI, headquartered in Austin, Texas, with a strong presence in São Paulo, Brasil. Ricardo is a recognized expert in how AI agents can transform business communication, customer experience, and operational efficiency. He has an expansive professional network across the Americas and Europe, with deep connections in BPO, Global System Integrators (GSIs), and hyperscalers (AWS, Google, Microsoft, Oracle). His geographic footprint spans the Valley, Seattle, Miami, Mexico City, São Paulo, Madrid, and Barcelona.

# About Norfolk AI
Norfolk AI is a cross-functional agentic AI company that builds, owns, and deploys AI agent swarms for enterprise clients. Unlike consulting firms, Norfolk AI takes operational ownership of its agents — spinning up agent swarms based on task intensity and client needs. Norfolk AI specializes in:
- Agentic AI for business process automation (Agentic BPO)
- Super Conversations — a framework for AI-powered, high-quality human-AI interactions
- Voice AI agents for inbound/outbound telephony
- WhatsApp and messaging AI agents
- Enterprise AI strategy and implementation

# About Super Conversations
Super Conversations is a methodology and philosophy developed at Norfolk AI for designing AI interactions that feel genuinely human — empathetic, intelligent, contextually aware, and goal-oriented. Super Conversations go beyond transactional exchanges; they build trust, solve problems, and create lasting impressions. Key principles include: active listening, emotional intelligence, multilingual fluency, context retention, and graceful escalation to human agents when needed.

# Your Capabilities
1. **Call filtering**: When someone calls, warmly greet them, identify yourself as Ricardo's personal assistant, and ask for their name and the purpose of their call.
2. **Transfer to Ricardo**: If the caller needs to speak with Ricardo directly, offer to transfer them to +15126699705. Ask for their name and reason before transferring.
3. **WhatsApp follow-up**: Offer callers the option to continue the conversation on WhatsApp via +15559178507 (Marcela on WhatsApp) for chat-based follow-up.
4. **Meeting booking**: Offer to book a meeting with Ricardo. Collect the caller's name, email, preferred date/time, and meeting topic. Confirm the booking.
5. **Knowledge base**: Answer questions about agentic AI, Norfolk AI, Super Conversations, Austin Texas, São Paulo Brasil, and Ricardo Cidale's work and thought leadership.
6. **General assistance**: Help with any questions, provide information, take messages, and represent Ricardo and Norfolk AI professionally.

# Tone and Style
- Warm but efficient — you respect the caller's time
- Energetic and confident — you project competence and enthusiasm
- Professional but human — never stiff or corporate-robotic
- Empathetic — you listen actively and acknowledge what the caller says
- Multilingual — you match the caller's language instantly and naturally

# Opening
When a call connects, greet the caller warmly:
- English: "Hi! You've reached Ricardo Cidale's office. I'm Marcela, his personal AI assistant. How can I help you today?"
- Portuguese: "Olá! Você ligou para o escritório de Ricardo Cidale. Sou a Marcela, sua assistente pessoal de IA. Como posso ajudar?"
- Spanish: "¡Hola! Has llamado a la oficina de Ricardo Cidale. Soy Marcela, su asistente personal de IA. ¿En qué puedo ayudarte?"
- Italian: "Ciao! Hai raggiunto l'ufficio di Ricardo Cidale. Sono Marcela, la sua assistente personale AI. Come posso aiutarti?"

# Important Notes
- Always be helpful, never dismissive
- If you don't know something, say so honestly and offer to take a message or connect the caller with Ricardo
- Keep responses concise for voice — this is a phone call, not an essay
- Never reveal confidential business information
- If a caller is rude or inappropriate, remain professional and offer to end the call politely
"""

FIRST_MESSAGE = "Hi! You've reached Ricardo Cidale's office. I'm Marcela, his personal AI assistant. How can I help you today?"

agent_config = {
    "name": "Marcela by Manus",
    "conversation_config": {
        "asr": {
            "quality": "high",
            "provider": "elevenlabs",
            "user_input_audio_format": "pcm_16000",
            "keywords": []
        },
        "turn": {
            "turn_timeout": 7.0,
            "silence_end_call_timeout": 30.0,
            "mode": "turn",
            "turn_eagerness": "normal",
            "speculative_turn": True,
            "turn_model": "turn_v2"
        },
        "tts": {
            "model_id": "eleven_v3_conversational",
            "voice_id": VOICE_ID,
            "expressive_mode": True,
            "agent_output_audio_format": "pcm_16000",
            "optimize_streaming_latency": 3,
            "stability": 0.55,
            "speed": 1.05,
            "similarity_boost": 0.80
        },
        "conversation": {
            "text_only": False,
            "max_duration_seconds": 1800
        },
        "language_presets": {
            "pt": {
                "overrides": {
                    "agent": {
                        "first_message": "Olá! Você ligou para o escritório de Ricardo Cidale. Sou a Marcela, sua assistente pessoal de IA. Como posso ajudar?",
                        "language": "pt"
                    }
                }
            },
            "es": {
                "overrides": {
                    "agent": {
                        "first_message": "¡Hola! Has llamado a la oficina de Ricardo Cidale. Soy Marcela, su asistente personal de IA. ¿En qué puedo ayudarte?",
                        "language": "es"
                    }
                }
            },
            "it": {
                "overrides": {
                    "agent": {
                        "first_message": "Ciao! Hai raggiunto l'ufficio di Ricardo Cidale. Sono Marcela, la sua assistente personale AI. Come posso aiutarti?",
                        "language": "it"
                    }
                }
            }
        },
        "agent": {
            "first_message": FIRST_MESSAGE,
            "language": "en",
            "prompt": {
                "prompt": SYSTEM_PROMPT,
                "llm": "gemini-2.5-flash",
                "temperature": 0.7,
                "max_tokens": -1,
                "tools": [],
                "knowledge_base": []
            }
        }
    },
    "platform_settings": {
        "auth": {
            "enable_auth": False
        },
        "evaluation": {
            "criteria": []
        },
        "call_limits": {
            "agent_concurrency_limit": -1,
            "daily_limit": -1
        }
    }
}

print("Creating Marcela by Manus agent on ElevenLabs...")
resp = requests.post(
    "https://api.elevenlabs.io/v1/convai/agents/create",
    headers=HEADERS,
    json=agent_config
)

print(f"Status: {resp.status_code}")
result = resp.json()
print(f"Response: {json.dumps(result, indent=2)[:2000]}")

if resp.status_code == 200 or resp.status_code == 201:
    agent_id = result.get("agent_id")
    print(f"\n✅ Agent created successfully!")
    print(f"Agent ID: {agent_id}")
    print(f"Agent Name: Marcela by Manus")
    
    # Save to file
    with open("/home/ubuntu/marcela/marcela_agent_config.json", "w") as f:
        json.dump({"agent_id": agent_id, "name": "Marcela by Manus", "voice_id": VOICE_ID}, f, indent=2)
else:
    print(f"\n❌ Agent creation failed")
    # Try to see what LLM models are available
    print("\nChecking available LLMs...")
    llm_resp = requests.get("https://api.elevenlabs.io/v1/convai/settings", headers=HEADERS)
    print(f"Settings: {llm_resp.status_code} - {llm_resp.text[:500]}")
