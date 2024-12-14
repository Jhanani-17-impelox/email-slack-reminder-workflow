# Workflow System Overview

This project defines a workflow system that involves three main agents (Email Agent, Slack Agent, and Workflow Agent) and several subgraphs to represent different parts of the process. The system integrates LangChain for handling language model queries, LangGraph for managing state graphs, and external services like Gmail and Slack for communication.

![image](https://github.com/user-attachments/assets/3d0c79d0-3988-456f-887b-add49ec5a914)


## Agents and Subagents

### EmailAgent

- **Uses LangChain:** Yes
- **Description:** Handles tasks related to email processing, such as checking for updates in the user's Gmail inbox or sending email reminders.
- **LangChain Integration:** Utilizes LangChain’s `ChatOpenAI` (a GPT-based model) to process user queries and communicates with Gmail via the `GmailToolkit`.
- **Methods:**
  - `process_query`: Uses LangChain’s agent executor (`create_react_agent`) to handle email-related queries.

### SlackAgent

- **Uses LangChain:** No
- **Description:** Sends reminder messages to a specified Slack channel. Directly interacts with the Slack API.
- **Slack SDK Integration:** Uses the `slack_sdk.WebClient` to send messages.
- **Methods:**
  - `send_slack_message`: Sends messages to a Slack channel.

### WorkUpdateWorkflow

- **Uses LangChain:** No
- **Description:** The main workflow agent that orchestrates the entire process. It combines multiple subgraphs (for checking email updates, checking time, sending reminders) and defines the logic for how these subgraphs should run in sequence based on certain conditions.
- **Methods:**
  - Defines and runs various subgraphs that execute individual steps of the workflow.

## Graphs and Subgraphs

The workflow is modular and split into multiple graphs and subgraphs, each representing specific tasks. These components allow for clean and flexible orchestration.

### 1. Time Check Subgraph

- **Graph Type:** Subgraph (StateGraph)
- **Purpose:** Checks the current time and stores it in the state.
- **Steps:**
  - A node that uses `check_time` to check the current time (using `datetime.now()`).
- **Use:** This subgraph is used by the main workflow to verify the time and make decisions based on it (e.g., whether to send a Slack reminder before 9 PM or an email reminder after 9 PM).

### 2. Email Update Check Subgraph

- **Graph Type:** Subgraph (StateGraph)
- **Purpose:** Checks whether an email update has been received from the user.
- **Steps:**
  - The `check_email_update` node sends a query to the `EmailAgent` to check if the user has sent a work update that day.
- **Use:** This subgraph determines whether a work update has been received, influencing whether a reminder should be sent.

### 3. Reminder Subgraph

- **Graph Type:** Subgraph (StateGraph)
- **Purpose:** Decides whether to send a Slack or email reminder based on the current time and whether an update has been received.
- **Steps:**
  - Two nodes (`send_slack_reminder` and `send_email_reminder`) are responsible for sending the reminders.
  - The graph uses a conditional entry point to decide which reminder (Slack or email) to send based on the `update_received` state and the time of day.
- **Use:** This subgraph handles the logic for sending reminders.

### 4. Main Workflow Graph

- **Graph Type:** Workflow (StateGraph)
- **Purpose:** Orchestrates the entire process by combining the subgraphs (email update check, time check, reminder sending).
- **Steps:**
  - Checks if an email update has been received.
  - If no update is received, it proceeds to check the time and potentially sends a reminder.
  - The graph has a conditional edge that decides whether to send a reminder or finish the workflow based on whether an update was received.

#### Flow of Execution:

1. **Email Update Check:** The main workflow starts by invoking the Email Update Check Subgraph, querying the Gmail account to see if an update email has been received.
2. **Time Check:** After checking for email updates, the Time Check Subgraph is invoked, verifying the current time.
3. **Reminder Sending:** 
   - If no email update was received and the time is before 9 PM, the Slack Reminder Subgraph is triggered to send a reminder to the user's Slack channel.
   - If no update was received and the time is after 9 PM, the Email Reminder Subgraph is triggered to send an email reminder to the user.
4. **Conditional Logic:** 
   - If an email update was received, the workflow ends.
   - If no update was received, it proceeds to check the time and send a reminder.

## LangChain vs Non-LangChain Agents

- **LangChain Agents:**
  - **EmailAgent:** Uses LangChain to interact with the Gmail API and process email-related queries using OpenAI's language model.
  - **WorkUpdateWorkflow:** The main workflow agent uses LangGraph (a graph-based framework) to manage the state transitions of multiple subgraphs.
  
- **Non-LangChain Agents:**
  - **SlackAgent:** This agent sends messages to Slack directly using the Slack API and does not interact with LangChain.

## Summary of Agents and Their Roles

- **EmailAgent:** Uses LangChain for querying email updates and sending email reminders.
- **SlackAgent:** Does not use LangChain; it directly interacts with Slack’s API to send reminders.
- **WorkUpdateWorkflow:** Orchestrates the entire process by using LangGraph and subgraphs to manage state transitions for checking email updates, time, and sending reminders.

This workflow ensures that users receive reminders based on whether they’ve provided a work update via email and the time of day, combining both email and Slack notifications into a seamless process.
