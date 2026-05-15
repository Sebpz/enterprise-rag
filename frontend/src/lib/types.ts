export type { Message, Citation, AgentStep, MessageRole, ChatMode } from "../hooks/useStreamingChat";

export interface EvalRun {
  id: number;
  config_version: string;
  faithfulness: number;
  answer_relevance: number;
  context_precision: number;
  context_recall: number;
  questions_tested: number;
  passed_regression: boolean;
  created_at: string;
}
