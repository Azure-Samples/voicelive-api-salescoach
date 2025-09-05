<!--
---
name: Voice Live API Sales Coach (Python + React)
description: A demo application showcasing AI-powered voice training for sales professionals using Azure Voice Live API and Azure AI services.
languages:
- python
- typescript
- bicep
- azdeveloper
products:
- azure-openai
- azure-ai-foundry
- azure-speech
- azure
page_type: sample
urlFragment: voicelive-api-salescoach
---
-->
<p align="center">
   <h1 align="center">Voice Live API: AI Sales Coach</h1>
</p>
<p align="center">A demo application showcasing AI-powered voice training for sales professionals, built on Azure.</p>
<p align="center">
   <a href="https://github.com/Azure-Samples/voicelive-api-salescoach/blob/main/LICENSE.md"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-green.svg" style="height:27px; vertical-align:middle;"/></a>
   <a href="https://github.com/Azure-Samples/voicelive-api-salescoach/actions/workflows/lint-and-test.yml"><img alt="Build Status" src="https://github.com/Azure-Samples/voicelive-api-salescoach/actions/workflows/lint-and-test.yml/badge.svg" style="height:27px; vertical-align:middle;"/></a>&nbsp;
   <a href="https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2FAzure-Samples%2Fvoicelive-api-salescoach%2Frefs%2Fheads%2Fmain%2Finfra%2Fdeployment.json"><img src="https://aka.ms/deploytoazurebutton" alt="Deploy to Azure" style="height:27px; vertical-align:middle;"/></a>&nbsp;
</p>

![Voice Live API Salescoach in Action](docs/assets/preview.png)

---

## Overview

Voice Live API Salescoach is a demo application showcasing how AI-based training could be used in sales education using Azure AI services. Practice real-world sales scenarios with AI-powered virtual customers, receive instant feedback on your performance, and improve your sales skills through immersive voice conversations.

### Features

- **Real-time Voice Conversations** - Practice sales calls with AI agents that respond naturally using Azure Voice Live API
- **Performance Analysis** - Get detailed feedback on your conversation skills
- **Pronunciation Assessment** - Improve your speaking clarity and confidence with Azure Speech Services
- **Scoring System** - Track your progress with metrics

![Performance Analysis Dashboard](docs/assets/analysis.png)

## Demo

See the Voice Live API Salescoach in action:

https://github.com/user-attachments/assets/904f1555-6981-4780-ae64-c5757337bcad

### How It Works

1. **Choose a Scenario** - Select from various industry-specific sales situations
2. **Start the Conversation** - Click the microphone to start your simulation
3. **Engage with AI** - The virtual customer responds realistically based on the scenario
4. **Receive Feedback** - Get instant analysis on your performance including:
   - Speaking tone and style
   - Content quality
   - Needs assessment
   - Value proposition delivery
   - Objection handling skills

## Getting Started

### Deploy to Azure

1. **Deploy to Azure**:
   ```bash
   azd up
   ```
2. **Access your application**:
   The deployment will output the URL where your application is running.

### Local Development

This project includes a dev container for easy setup and a build script for  development.

1. **Use Dev Container** (Recommended)
   - Open in VS Code and select "Reopen in Container" when prompted
   - All dependencies and tools are pre-configured

2. **Fill in the .env file**
   - Copy `.env.template` to `.env`
   - Fill in your Azure AI Foundry and Speech service keys and endpoints (you can run `azd provision` to create these resources if you haven't already)

3. **Build and run**
   ```bash
   # Build the application
   ./scripts/build.sh

   # Start the server
   cd backend && python src/app.py
   ```

Visit `http://localhost:8000` to start training!

## Architecture

<table>
<tr>
<td width="400">
<img src="docs/assets/architecture.png" alt="Architecture Diagram" width="500"/>
</td>
<td>

The application leverages multiple Azure AI services to deliver real-time voice-based sales training:

- **Azure AI Foundry** - AI platform including:
  - Voice Live API for real-time speech-to-speech conversations and avatar simulation
  - Large language models (GPT-4o) as underlying LLM for performance analysis
  - Speech Services for post-conversation pronunciation and fluency assessment
  - Optional AI Agent Service
- **React + Fluent UI** - Modern web interface
- **Python Flask** - Backend API and WebSocket communication

**Conversation Flow:** User speech → Voice Live API → GPT-4o processing → AI agent response → Performance analysis → Detailed feedback

</td>
</tr>
</table>


## Contributors
<p float="left">
  <a href="https://github.com/aymenfurter"><img src="https://github.com/aymenfurter.png" width="100" height="100" alt="aymenfurter" style="border-radius:50%;"/></a>
  <a href="https://github.com/curia-damiano"><img src="https://github.com/curia-damiano.png" width="100" height="100" alt="curia-damiano" style="border-radius:50%;"/></a>
  <a href="https://github.com/TiffanyZ4Msft"><img src="https://github.com/TiffanyZ4Msft.png" width="100" height="100" alt="TiffanyZ4Msft.png" style="border-radius:50%;"/></a>
</p>

## Contributing

This project welcomes contributions and suggestions. Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.opensource.microsoft.com.

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Security

Microsoft takes the security of our software products and services seriously, which includes all source code repositories managed through our GitHub organizations, which include [Microsoft](https://github.com/Microsoft), [Azure](https://github.com/Azure), [DotNet](https://github.com/dotnet), [AspNet](https://github.com/aspnet) and [Xamarin](https://github.com/xamarin).

If you believe you have found a security vulnerability in any Microsoft-owned repository that meets [Microsoft's definition of a security vulnerability](https://aka.ms/security.md/definition), please report it to us as described in [SECURITY.md](SECURITY.md).

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft
trademarks or logos is subject to and must follow
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.
Any use of third-party trademarks or logos are subject to those third-party's policies.



<p align="center">
   <br/>
   <br/>
   Made with ❤️ in 🇨🇭
</p>
