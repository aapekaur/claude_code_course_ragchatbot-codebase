import anthropic
from typing import List, Optional, Dict, Any

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    MAX_TOOL_ROUNDS = 2

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to a comprehensive search tool for course information.

Search Tool Usage:
- Use the **search_course_content** tool only for questions about specific course content or detailed educational materials
- Use the **get_course_outline** tool for questions about course structure, lesson lists, or outlines
- **Up to two sequential searches per query** — use a follow-up search only when the first result is insufficient to fully answer the question
- Synthesize search results into accurate, fact-based responses
- If search yields no results, state this clearly without offering alternatives
- When returning a course outline, include the course title, course link, and all lesson numbers and titles

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without searching
- **Course-specific questions**: Search first, then answer
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, search explanations, or question-type analysis
 - Do not mention "based on the search results"


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }

    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional tool usage and conversation context.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """

        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        # Prepare API call parameters efficiently
        api_params = {
            **self.base_params,
            "messages": [{"role": "user", "content": query}],
            "system": system_content
        }

        # Add tools if available
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}

        # Get response from Claude
        response = self.client.messages.create(**api_params)

        # Handle tool execution if needed
        if response.stop_reason == "tool_use" and tool_manager:
            return self._run_tool_loop(
                initial_response=response,
                messages=api_params["messages"].copy(),
                tools=tools,
                system=system_content,
                tool_manager=tool_manager,
            )

        # Return direct response
        return response.content[0].text

    def _run_tool_loop(self, initial_response, messages, tools, system, tool_manager) -> str:
        """
        Execute up to MAX_TOOL_ROUNDS of tool-calling, then return the final answer.

        Each round keeps tools available so Claude can chain searches when needed.
        If Claude stops naturally (stop_reason != "tool_use") during the loop,
        its response is returned immediately. If all rounds are exhausted while
        Claude still wants tools, remaining tools are executed and a final
        synthesis call (without tools) is made.

        Args:
            initial_response: The first response containing tool use requests
            messages: Accumulated message history (copy from generate_response)
            tools: Tool definitions to keep available between rounds
            system: System prompt string
            tool_manager: Manager to execute tools

        Returns:
            Final response text
        """
        current = initial_response

        for _ in range(self.MAX_TOOL_ROUNDS):
            # Append assistant's tool-use turn to history
            messages.append({"role": "assistant", "content": current.content})

            # Execute every tool_use block; errors are passed as content so Claude can adapt
            tool_results = []
            for block in current.content:
                if block.type == "tool_use":
                    result = tool_manager.execute_tool(block.name, **block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            messages.append({"role": "user", "content": tool_results})

            # Call API with tools so Claude can decide to search again
            current = self.client.messages.create(
                **self.base_params,
                messages=messages,
                system=system,
                tools=tools,
                tool_choice={"type": "auto"},
            )

            if current.stop_reason != "tool_use":
                # Claude answered naturally — return directly, no extra synthesis call
                return current.content[0].text

        # Rounds exhausted and Claude still wants tools:
        # execute the pending tools, then synthesize without tool pressure
        messages.append({"role": "assistant", "content": current.content})
        tool_results = []
        for block in current.content:
            if block.type == "tool_use":
                result = tool_manager.execute_tool(block.name, **block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })
        messages.append({"role": "user", "content": tool_results})

        final = self.client.messages.create(
            **self.base_params,
            messages=messages,
            system=system,
        )
        return final.content[0].text
