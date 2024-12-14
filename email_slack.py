import os
import json
import datetime
from typing import TypedDict, List, Optional, Dict, Any

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent
from langchain_google_community import GmailToolkit
from langchain_google_community.gmail.utils import (
    build_resource_service,
    get_gmail_credentials,
)
import slack_sdk
from slack_sdk.errors import SlackApiError
import operator
from typing import Annotated

class EmailAgent:
    """
    An independent Email Agent node for LangGraph that handles email-related tasks 
    such as email extraction, sending emails, or any user-defined query through Gmail API.
    """

    def __init__(self):
        # Initialize Gmail credentials and API resource
        self.credentials = get_gmail_credentials(
            token_file="token.json",
            scopes=["https://mail.google.com/"],
            client_secrets_file="credentials.json",
        )
        self.api_resource = build_resource_service(credentials=self.credentials)

        # Initialize Gmail Toolkit
        self.toolkit = GmailToolkit(api_resource=self.api_resource)

        # Initialize OpenAI LLM
        os.environ["OPENAI_API_KEY"] = "your-api-key"
        self.llm = ChatOpenAI(model="gpt-4o-mini")

        # Create the LangGraph REACT agent for the Email Agent node
        self.agent_executor = create_react_agent(self.llm, self.toolkit.get_tools())

    def process_query(self, query):
        """
        Processes the user's email-related query and streams the results back.

        Args:
            query (str): User-defined email search query or instruction.

        Returns:
            list: Extracted data or response messages.
        """
        events = self.agent_executor.stream(
            {"messages": [("user", query)]}, stream_mode="values"
        )

        extracted_data = []
        for event in events:
            message = event["messages"][-1]
            extracted_data.append(message)

        return extracted_data

class SlackAgent:
    """
    Slack Agent for sending reminder messages.
    """
    def __init__(self, slack_token, channel_id):
        self.client = slack_sdk.WebClient(token=slack_token)
        self.channel_id = channel_id

    def send_slack_message(self, message):
        """
        Send a Slack message to a specified channel.
        
        Args:
            message (str): Message to be sent.
        
        Returns:
            bool: True if message sent successfully, False otherwise.
        """
        try:
            response = self.client.chat_postMessage(
                channel=self.channel_id,
                text=message
            )
            return True
        except SlackApiError as e:
            print(f"Error sending Slack message: {e}")
            return False



class WorkUpdateState(TypedDict):
    user_email: str
    update_received: Annotated[bool, operator.or_]  # Reducer for logical OR of multiple updates
    current_time: datetime.datetime
    reminder_sent: Annotated[bool, operator.or_]  # Combine reminder_sent states
    slack_message_sent: bool
    email_agent: Optional[EmailAgent]
    slack_agent: Optional[SlackAgent]


class WorkUpdateWorkflow:
    def __init__(self, user_email):
        # Initialize Email and Slack Agents
        self.email_agent = EmailAgent()
        self.slack_agent = SlackAgent(
            slack_token="enter-your-slack-token",
            channel_id="enter-channel-id"
        )

        # Build Time Check Subgraph
        time_check_graph = StateGraph(WorkUpdateState)
        time_check_graph.add_node("check_time", self.check_time)
        time_check_graph.add_edge(START, "check_time")
        time_check_graph.add_edge("check_time", END)
        self.time_check_subgraph = time_check_graph.compile()
        
        # Build Email Update Subgraph
        email_update_graph = StateGraph(WorkUpdateState)
        email_update_graph.add_node("check_email_update", self.check_email_update)
        email_update_graph.add_edge(START, "check_email_update")
        email_update_graph.add_edge("check_email_update", END)
        self.email_update_subgraph = email_update_graph.compile()

        # Build Reminder Subgraph
        reminder_graph = StateGraph(WorkUpdateState)
        reminder_graph.add_node("send_slack_reminder", self.send_slack_reminder)
        reminder_graph.add_node("send_email_reminder", self.send_email_reminder)
        reminder_graph.add_edge(START, "send_slack_reminder")
        reminder_graph.set_conditional_entry_point(
            lambda state: "send_slack_reminder" 
            if not state["update_received"] and state["current_time"].time() < datetime.time(21,0)
            else "send_email_reminder"
        )
        reminder_graph.add_edge("send_slack_reminder", END)
        reminder_graph.add_edge("send_email_reminder", END)
        self.reminder_subgraph = reminder_graph.compile()

        # Main Workflow Graph
        builder = StateGraph(WorkUpdateState)
        
        # Add nodes
        builder.add_node("email_update_check", self.run_email_update_subgraph)
        builder.add_node("time_check", self.run_time_check_subgraph)
        builder.add_node("send_reminder", self.run_reminder_subgraph)
        
        # Define edges
        builder.add_edge(START, "email_update_check")
        builder.add_edge("email_update_check", "time_check")
        
        # Conditional edge for reminders
        builder.add_conditional_edges(
            "time_check",
            lambda state: "send_reminder" if not state["update_received"] else END
        )
        
        builder.add_edge("send_reminder", END)
        
        # Compile the main workflow
        self.workflow = builder.compile()

    def check_email_update(self, state: WorkUpdateState):
        """
        Subgraph to check if an email update has been received.
        """
        print("🔍 Checking for email updates...")  # Debugging print
        query = f"Check if {state['user_email']} has sent a work update today"
        results = self.email_agent.process_query(query)
        
        # Determine if an update was received based on results
        update_received = any('work update found' in result.content.lower() for result in results)
        print(f"📧 Email update check: {update_received}")  # Debugging print
        
        return {
            **state,
            "update_received": update_received
        }

    def check_time(self, state: WorkUpdateState):
        """
        Subgraph to check the current time.
        """
        print("⏰ Checking the current time...")  # Debugging print
        current_time = datetime.datetime.now()
        print(f"🕒 Current time: {current_time}")  # Debugging print
        
        return {
            **state,
            "current_time": current_time
        }

    def send_slack_reminder(self, state: WorkUpdateState):
        """
        Subgraph to send a Slack reminder before 9 PM.
        """
        print("🔔 Sending Slack reminder...")  # Debugging print
        message = f"Reminder: Please send your work update via email to {state['user_email']}"
        slack_sent = self.slack_agent.send_slack_message(message)
        print(f"✅ Slack reminder sent: {slack_sent}")  # Debugging print
        
        return {
            **state,
            "slack_message_sent": slack_sent,
            "reminder_sent": slack_sent
        }

    def send_email_reminder(self, state: WorkUpdateState):
        """
        Subgraph to send an email reminder after 9 PM.
        """
        print("📧 Sending email reminder...")  # Debugging print
        query = f"Send an email to {state['user_email']} reminding them to send their work update"
        results = self.email_agent.process_query(query)
        
        email_sent = any('email sent' in result.content.lower() for result in results)
        print(f"✅ Email reminder sent: {email_sent}")  # Debugging print
        
        return {
            **state,
            "reminder_sent": email_sent
        }

    def run_email_update_subgraph(self, state: WorkUpdateState):
        """
        Run the email update check subgraph.
        """
        return self.email_update_subgraph.invoke(state)

    def run_time_check_subgraph(self, state: WorkUpdateState):
        """
        Run the time check subgraph.
        """
        return self.time_check_subgraph.invoke(state)

    def run_reminder_subgraph(self, state: WorkUpdateState):
        """
        Run the reminder subgraph.
        """
        return self.reminder_subgraph.invoke(state)

    def run_workflow(self):
        """
        Execute the entire workflow for a specific user.
        """
        initial_state = {
            "user_email": "jhananinallasamy1234@gmail.com",
            "update_received": False,
            "current_time": datetime.datetime.now(),
            "reminder_sent": False,
            "slack_message_sent": False,
            "email_agent": self.email_agent,
            "slack_agent": self.slack_agent
        }

        # Stream the workflow
        for chunk in self.workflow.stream(initial_state):
            print(f"💡 Workflow progress: {chunk}")  # Debugging print

def main():
    workflow = WorkUpdateWorkflow("jhananinallasamy@gmail.com")
    workflow.run_workflow()

if __name__ == "__main__":
    main()
