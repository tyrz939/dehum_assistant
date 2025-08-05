# Dehumidifier Assistant

This repository contains the full codebase for the Dehumidifier Assistant, a comprehensive business tool designed to qualify leads, provide accurate sizing calculations, and seamlessly hand off complex cases to human experts. The project is architected as a two-tier system, combining a WordPress plugin for the user interface with a Python AI service for intelligence.

## Core Architecture

The system is currently built as a two-tier architecture:

-   **WordPress Plugin (`dehum-assistant-mvp`)**: Handles the frontend chat interface, Elementor integration, conversation logging, and the admin dashboard. This layer is responsible for all user interactions and data presentation.
-   **Python AI Service (`python-ai-service`)**: The intelligence layer of the application. It features a model-agnostic AI agent with tools for dehumidifier sizing, product lookups, and technical reference, now including a Retrieval-Augmented Generation (RAG) pipeline for answering questions from a knowledge base. This service is built with FastAPI and supports various AI models, including OpenAI, Claude, and Gemini, through LiteLLM.

Here is a simplified text-based overview of the data flow:

1.  **User** -> interacts with -> **WordPress Plugin (Chat Widget)**
2.  **WordPress Plugin** -> sends HTTP request to -> **Python AI Service (FastAPI)**
3.  **Python AI Service** -> processes request with -> **AI Agent**
    - The AI Agent uses its tools:
        - Sizing Calculator
        - Product Recommendations
        - RAG Pipeline
4.  **Python AI Service** -> sends AI response to -> **WordPress Plugin**
5.  **WordPress Plugin** -> displays response to User and logs conversation in -> **WP Database**
6.  **Admin** -> views logs via -> **Admin Dashboard**

## Features

-   **AI-Powered Chat**: A responsive chat widget with AI-driven assistance.
-   **Retrieval-Augmented Generation (RAG)**: The AI can now answer questions by retrieving information from a dedicated knowledge base of product manuals and technical documents.
-   **Professional Admin Interface**: Tools for viewing and managing conversation logs.
-   **Advanced Sizing Calculations**: Accurate dehumidifier sizing based on detailed room and environmental parameters.
-   **Product Recommendations**: Intelligent product matching from a predefined catalog.
-   **Session Management**: Persistent conversation history and context.
-   **Elementor Integration**: Easily place the chat widget anywhere on a WordPress site.
-   **Business Automation**: Automated lead scoring, email notifications, and CRM integration.

## Quick Start

### WordPress Plugin

1.  **Installation**:
    *   Navigate to the `dehum-assistant-mvp` directory.
    *   Zip the contents of the directory.
    *   Upload the zip file to your WordPress site via the plugin installer.
    *   Alternatively, you can manually copy the directory to `wp-content/plugins`.
2.  **Activation**:
    *   Activate the plugin from the WordPress admin dashboard.
    *   Configure the AI service URL and other settings in the plugin's admin page.

### Python AI Service

1.  **Environment Setup**:
    *   Navigate to the `python-ai-service` directory.
    *   Create and activate a virtual environment.
    *   Install the required dependencies: `pip install -r requirements.txt`.
2.  **Configuration**:
    *   Create a `.env` file from the `env.example` template.
    *   Add your OpenAI API key and any other necessary configurations.
3.  **Building the RAG Index**:
    *   To use the RAG capabilities, you first need to build the vector index from your documents.
    *   Run the script: `python build_rag_index.py`.
4.  **Running the Service**:
    *   Start the service with `uvicorn main:app --host 0.0.0.0 --port 8000 --reload`.
    *   The service will be available at `http://localhost:8000`.

## Project Structure

The repository is organized into two main directories:

-   `dehum-assistant-mvp/`: Contains the WordPress plugin, including all PHP, CSS, and JS files.
-   `python-ai-service/`: Contains the FastAPI application, including the AI agent, tools, RAG pipeline, and configuration.

## Roadmap

For detailed information on the project's future development plans, please refer to the [ROADMAP.md](ROADMAP.md) file. This file outlines the upcoming features, implementation priorities, and long-term vision for the project.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
