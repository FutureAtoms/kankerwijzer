"use client";
import type { UseChatHelpers } from "@ai-sdk/react";
import type { Vote } from "@/lib/db/schema";
import type { ChatMessage } from "@/lib/types";
import { cn, sanitizeText } from "@/lib/utils";
import {
  ActivityIcon,
  BarChart3Icon,
  BookOpenIcon,
  DatabaseIcon,
  ExternalLinkIcon,
  MapPinIcon,
  SearchIcon,
} from "lucide-react";
import { MessageContent, MessageResponse } from "../ai-elements/message";
import { Shimmer } from "../ai-elements/shimmer";
import {
  Tool,
  ToolContent,
  ToolHeader,
  ToolInput,
  ToolOutput,
} from "../ai-elements/tool";
import { useDataStream } from "./data-stream-provider";
import { DocumentToolResult } from "./document";
import { DocumentPreview } from "./document-preview";
import { SparklesIcon } from "./icons";
import { MessageActions } from "./message-actions";
import { MessageReasoning } from "./message-reasoning";
import { PreviewAttachment } from "./preview-attachment";
import { Weather } from "./weather";

const PurePreviewMessage = ({
  addToolApprovalResponse,
  chatId,
  message,
  vote,
  isLoading,
  setMessages: _setMessages,
  regenerate: _regenerate,
  isReadonly,
  requiresScrollPadding: _requiresScrollPadding,
  onEdit,
}: {
  addToolApprovalResponse: UseChatHelpers<ChatMessage>["addToolApprovalResponse"];
  chatId: string;
  message: ChatMessage;
  vote: Vote | undefined;
  isLoading: boolean;
  setMessages: UseChatHelpers<ChatMessage>["setMessages"];
  regenerate: UseChatHelpers<ChatMessage>["regenerate"];
  isReadonly: boolean;
  requiresScrollPadding: boolean;
  onEdit?: (message: ChatMessage) => void;
}) => {
  const attachmentsFromMessage = message.parts.filter(
    (part) => part.type === "file"
  );

  useDataStream();

  const isUser = message.role === "user";
  const isAssistant = message.role === "assistant";

  const hasAnyContent = message.parts?.some(
    (part) =>
      (part.type === "text" && part.text?.trim().length > 0) ||
      (part.type === "reasoning" &&
        "text" in part &&
        part.text?.trim().length > 0) ||
      part.type.startsWith("tool-")
  );
  const isThinking = isAssistant && isLoading && !hasAnyContent;

  const attachments = attachmentsFromMessage.length > 0 && (
    <div
      className="flex flex-row justify-end gap-2"
      data-testid={"message-attachments"}
    >
      {attachmentsFromMessage.map((attachment) => (
        <PreviewAttachment
          attachment={{
            name: attachment.filename ?? "file",
            contentType: attachment.mediaType,
            url: attachment.url,
          }}
          key={attachment.url}
        />
      ))}
    </div>
  );

  const mergedReasoning = message.parts?.reduce(
    (acc, part) => {
      if (part.type === "reasoning" && part.text?.trim().length > 0) {
        return {
          text: acc.text ? `${acc.text}\n\n${part.text}` : part.text,
          isStreaming: "state" in part ? part.state === "streaming" : false,
          rendered: false,
        };
      }
      return acc;
    },
    { text: "", isStreaming: false, rendered: false }
  ) ?? { text: "", isStreaming: false, rendered: false };

  const parts = message.parts?.map((part, index) => {
    const { type } = part;
    const key = `message-${message.id}-part-${index}`;

    if (type === "reasoning") {
      if (!mergedReasoning.rendered && mergedReasoning.text) {
        mergedReasoning.rendered = true;
        return (
          <MessageReasoning
            isLoading={isLoading || mergedReasoning.isStreaming}
            key={key}
            reasoning={mergedReasoning.text}
          />
        );
      }
      return null;
    }

    if (type === "text") {
      return (
        <MessageContent
          className={cn("text-[13px] leading-[1.65]", {
            "w-fit max-w-[min(80%,56ch)] overflow-hidden break-words rounded-2xl rounded-br-lg border border-border/30 bg-gradient-to-br from-secondary to-muted px-3.5 py-2 shadow-[var(--shadow-card)]":
              message.role === "user",
          })}
          data-testid="message-content"
          key={key}
        >
          <MessageResponse>{sanitizeText(part.text)}</MessageResponse>
        </MessageContent>
      );
    }

    if (type === "tool-getWeather") {
      const { toolCallId, state } = part;
      const approvalId = (part as { approval?: { id: string } }).approval?.id;
      const isDenied =
        state === "output-denied" ||
        (state === "approval-responded" &&
          (part as { approval?: { approved?: boolean } }).approval?.approved ===
            false);
      const widthClass = "w-[min(100%,450px)]";

      if (state === "output-available") {
        return (
          <div className={widthClass} key={toolCallId}>
            <Weather weatherAtLocation={part.output} />
          </div>
        );
      }

      if (isDenied) {
        return (
          <div className={widthClass} key={toolCallId}>
            <Tool className="w-full" defaultOpen={true}>
              <ToolHeader state="output-denied" type="tool-getWeather" />
              <ToolContent>
                <div className="px-4 py-3 text-muted-foreground text-sm">
                  Weather lookup was denied.
                </div>
              </ToolContent>
            </Tool>
          </div>
        );
      }

      if (state === "approval-responded") {
        return (
          <div className={widthClass} key={toolCallId}>
            <Tool className="w-full" defaultOpen={true}>
              <ToolHeader state={state} type="tool-getWeather" />
              <ToolContent>
                <ToolInput input={part.input} />
              </ToolContent>
            </Tool>
          </div>
        );
      }

      return (
        <div className={widthClass} key={toolCallId}>
          <Tool className="w-full" defaultOpen={true}>
            <ToolHeader state={state} type="tool-getWeather" />
            <ToolContent>
              {(state === "input-available" ||
                state === "approval-requested") && (
                <ToolInput input={part.input} />
              )}
              {state === "approval-requested" && approvalId && (
                <div className="flex items-center justify-end gap-2 border-t px-4 py-3">
                  <button
                    className="rounded-md px-3 py-1.5 text-muted-foreground text-sm transition-colors hover:bg-muted hover:text-foreground"
                    onClick={() => {
                      addToolApprovalResponse({
                        id: approvalId,
                        approved: false,
                        reason: "User denied weather lookup",
                      });
                    }}
                    type="button"
                  >
                    Deny
                  </button>
                  <button
                    className="rounded-md bg-primary px-3 py-1.5 text-primary-foreground text-sm transition-colors hover:bg-primary/90"
                    onClick={() => {
                      addToolApprovalResponse({
                        id: approvalId,
                        approved: true,
                      });
                    }}
                    type="button"
                  >
                    Allow
                  </button>
                </div>
              )}
            </ToolContent>
          </Tool>
        </div>
      );
    }

    if (type === "tool-createDocument") {
      const { toolCallId } = part;

      if (part.output && "error" in part.output) {
        return (
          <div
            className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-500 dark:bg-red-950/50"
            key={toolCallId}
          >
            Error creating document: {String(part.output.error)}
          </div>
        );
      }

      return (
        <DocumentPreview
          isReadonly={isReadonly}
          key={toolCallId}
          result={part.output}
        />
      );
    }

    if (type === "tool-updateDocument") {
      const { toolCallId } = part;

      if (part.output && "error" in part.output) {
        return (
          <div
            className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-500 dark:bg-red-950/50"
            key={toolCallId}
          >
            Error updating document: {String(part.output.error)}
          </div>
        );
      }

      return (
        <div className="relative" key={toolCallId}>
          <DocumentPreview
            args={{ ...part.output, isUpdate: true }}
            isReadonly={isReadonly}
            result={part.output}
          />
        </div>
      );
    }

    if (type === "tool-requestSuggestions") {
      const { toolCallId, state } = part;

      return (
        <Tool
          className="w-[min(100%,450px)]"
          defaultOpen={true}
          key={toolCallId}
        >
          <ToolHeader state={state} type="tool-requestSuggestions" />
          <ToolContent>
            {state === "input-available" && <ToolInput input={part.input} />}
            {state === "output-available" && (
              <ToolOutput
                errorText={undefined}
                output={
                  "error" in part.output ? (
                    <div className="rounded border p-2 text-red-500">
                      Error: {String(part.output.error)}
                    </div>
                  ) : (
                    <DocumentToolResult
                      isReadonly={isReadonly}
                      result={part.output}
                      type="request-suggestions"
                    />
                  )
                }
              />
            )}
          </ToolContent>
        </Tool>
      );
    }

    if (type === "tool-searchSources") {
      const { toolCallId, state } = part;

      return (
        <div className="w-full" key={toolCallId}>
          <Tool className="w-full" defaultOpen={true}>
            <ToolHeader
              state={state}
              title="Zoeken in kanker.nl bronnen"
              type="tool-searchSources"
            />
            <ToolContent>
              {(state === "input-available" ||
                state === "input-streaming") && (
                <>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                    <SearchIcon className="size-4" />
                    <span>Zoeken in 2816 kanker.nl pagina&apos;s...</span>
                  </div>
                  <ToolInput input={part.input} />
                </>
              )}
              {state === "output-available" && part.output && (
                <>
                  <div className="flex items-center gap-2 text-sm mb-2">
                    <BookOpenIcon className="size-4 text-emerald-600" />
                    <span className="font-medium">
                      {(() => {
                        const out = part.output as unknown as Record<string, unknown>;
                        const count = out?.resultCount;
                        return typeof count === "number"
                          ? `${count} bronnen gevonden`
                          : "Bronnen gevonden";
                      })()}
                    </span>
                  </div>
                  {/* Render individual source results */}
                  {(() => {
                    const out = part.output as unknown as Record<string, unknown>;
                    const results = out?.results as Array<Record<string, unknown>> | undefined;
                    if (!results?.length) return null;
                    return (
                      <div className="space-y-3">
                        {results.map((result, idx) => (
                          <div
                            key={`${toolCallId}-result-${idx}`}
                            className="rounded-md border bg-muted/30 p-3"
                          >
                            <div className="flex items-start gap-2 mb-1">
                              <ExternalLinkIcon className="size-3.5 mt-0.5 text-blue-500 shrink-0" />
                              <a
                                href={String(result.url)}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-xs text-blue-600 hover:underline break-all"
                              >
                                {String(result.url)}
                              </a>
                            </div>
                            <blockquote className="border-l-2 border-emerald-500 pl-3 text-sm text-foreground/90 italic">
                              &ldquo;{String(result.exactText)}&rdquo;
                            </blockquote>
                            <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                              {typeof result.cancerType === "string" ? (
                                  <span className="bg-muted px-1.5 py-0.5 rounded">
                                    {result.cancerType}
                                  </span>
                                ) : null}
                              {typeof result.relevanceScore === "number" && (
                                <span>score: {String(result.relevanceScore)}</span>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    );
                  })()}
                </>
              )}
              {state === "output-error" && (
                <ToolOutput errorText={part.errorText} output={part.output} />
              )}
            </ToolContent>
          </Tool>
        </div>
      );
    }

    if (type === "tool-getNkrStatistics") {
      const { toolCallId, state } = part;
      const widthClass = "w-full";

      return (
        <div className={widthClass} key={toolCallId}>
          <Tool className="w-full" defaultOpen={true}>
            <ToolHeader
              state={state}
              title="NKR Cancer Statistics"
              type="tool-getNkrStatistics"
            />
            <ToolContent>
              {(state === "input-available" ||
                state === "input-streaming") && (
                <>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                    <BarChart3Icon className="size-4" />
                    <span>Querying Netherlands Cancer Registry...</span>
                  </div>
                  <ToolInput input={part.input} />
                </>
              )}
              {state === "output-available" && (
                <>
                  <div className="flex items-center gap-2 text-sm mb-2">
                    <DatabaseIcon className="size-4 text-green-600" />
                    <span className="font-medium">
                      Source: {String((part.output as unknown as Record<string, unknown>)?.source ?? "nkr-cijfers.iknl.nl")}
                    </span>
                    {typeof (part.output as unknown as Record<string, unknown>)?.topic === "string" ? (
                      <span className="text-muted-foreground">
                        — {String((part.output as unknown as Record<string, unknown>).topic)}
                      </span>
                    ) : null}
                  </div>
                  <ToolInput input={part.input} />
                  <ToolOutput errorText={part.errorText} output={part.output} />
                </>
              )}
              {state === "output-error" && (
                <ToolOutput errorText={part.errorText} output={part.output} />
              )}
            </ToolContent>
          </Tool>
        </div>
      );
    }

    if (type === "tool-getCancerAtlasData") {
      const { toolCallId, state } = part;
      const widthClass = "w-full";

      return (
        <div className={widthClass} key={toolCallId}>
          <Tool className="w-full" defaultOpen={true}>
            <ToolHeader
              state={state}
              title="Cancer Atlas — Regional Data"
              type="tool-getCancerAtlasData"
            />
            <ToolContent>
              {(state === "input-available" ||
                state === "input-streaming") && (
                <>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                    <MapPinIcon className="size-4" />
                    <span>Querying IKNL Cancer Atlas...</span>
                  </div>
                  <ToolInput input={part.input} />
                </>
              )}
              {state === "output-available" && (
                <>
                  <div className="flex items-center gap-2 text-sm mb-2">
                    <ActivityIcon className="size-4 text-blue-600" />
                    <span className="font-medium">
                      Source: {String((part.output as unknown as Record<string, unknown>)?.source ?? "kankeratlas.iknl.nl")}
                    </span>
                    {typeof (part.output as unknown as Record<string, unknown>)?.description === "string" ? (
                      <span className="text-muted-foreground text-xs ml-1">
                        — {String((part.output as unknown as Record<string, unknown>).description)}
                      </span>
                    ) : null}
                  </div>
                  <ToolInput input={part.input} />
                  <ToolOutput errorText={part.errorText} output={part.output} />
                </>
              )}
              {state === "output-error" && (
                <ToolOutput errorText={part.errorText} output={part.output} />
              )}
            </ToolContent>
          </Tool>
        </div>
      );
    }

    // Generic fallback for any other tool calls (edit-document, etc.)
    if (type.startsWith("tool-")) {
      const toolPart = part as { toolCallId: string; state: string; input?: Record<string, unknown>; output?: Record<string, unknown>; errorText?: string };
      return (
        <div className="w-full" key={toolPart.toolCallId}>
          <Tool className="w-full" defaultOpen={true}>
            <ToolHeader
              state={toolPart.state as "input-available"}
              title={type.replace("tool-", "")}
              type={type as "tool-getWeather"}
            />
            <ToolContent>
              {toolPart.input != null ? <ToolInput input={toolPart.input} /> : null}
              {toolPart.output != null ? (
                <ToolOutput errorText={toolPart.errorText} output={toolPart.output} />
              ) : null}
            </ToolContent>
          </Tool>
        </div>
      );
    }

    return null;
  });

  const actions = !isReadonly && (
    <MessageActions
      chatId={chatId}
      isLoading={isLoading}
      key={`action-${message.id}`}
      message={message}
      onEdit={onEdit ? () => onEdit(message) : undefined}
      vote={vote}
    />
  );

  const content = isThinking ? (
    <div className="flex h-[calc(13px*1.65)] items-center text-[13px] leading-[1.65]">
      <Shimmer className="font-medium" duration={1}>
        Thinking...
      </Shimmer>
    </div>
  ) : (
    <>
      {attachments}
      {parts}
      {actions}
    </>
  );

  return (
    <div
      className={cn(
        "group/message w-full",
        !isAssistant && "animate-[fade-up_0.25s_cubic-bezier(0.22,1,0.36,1)]"
      )}
      data-role={message.role}
      data-testid={`message-${message.role}`}
    >
      <div
        className={cn(
          isUser ? "flex flex-col items-end gap-2" : "flex items-start gap-3"
        )}
      >
        {isAssistant && (
          <div className="flex h-[calc(13px*1.65)] shrink-0 items-center">
            <div className="flex size-7 items-center justify-center rounded-lg bg-muted/60 text-muted-foreground ring-1 ring-border/50">
              <SparklesIcon size={13} />
            </div>
          </div>
        )}
        {isAssistant ? (
          <div className="flex min-w-0 flex-1 flex-col gap-2">{content}</div>
        ) : (
          content
        )}
      </div>
    </div>
  );
};

export const PreviewMessage = PurePreviewMessage;

export const ThinkingMessage = () => {
  return (
    <div
      className="group/message w-full"
      data-role="assistant"
      data-testid="message-assistant-loading"
    >
      <div className="flex items-start gap-3">
        <div className="flex h-[calc(13px*1.65)] shrink-0 items-center">
          <div className="flex size-7 items-center justify-center rounded-lg bg-muted/60 text-muted-foreground ring-1 ring-border/50">
            <SparklesIcon size={13} />
          </div>
        </div>

        <div className="flex h-[calc(13px*1.65)] items-center text-[13px] leading-[1.65]">
          <Shimmer className="font-medium" duration={1}>
            Thinking...
          </Shimmer>
        </div>
      </div>
    </div>
  );
};
