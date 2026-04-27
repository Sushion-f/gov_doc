export interface AgentLoopEvent {
  seqNo?: number;
  eventType?: string;
  title?: string;
  detail?: string;
  detailHtml?: string;
  payload?: Record<string, unknown>;
  display?: {
    visible?: boolean;
    title?: string;
    subtitle?: string;
    status?: string;
    replace?: boolean;
    cardKey?: string;
  };
}

export interface SSEHandlers {
  onEvent: (event: AgentLoopEvent) => void;
  onDone: () => void;
  onError: (error: Error) => void;
}

export function createSSEConnection(streamUrl: string, handlers: SSEHandlers): { close: () => void } {
  const controller = new AbortController();

  const parseAndEmit = (buffer: string) => {
    const blocks = buffer.split('\n\n');
    return {
      rest: blocks.pop() || '',
      blocks,
    };
  };

  void fetch(streamUrl, {
    credentials: 'include',
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok || !response.body) {
        throw new Error(`SSE 连接失败: ${response.status}`);
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) {
          handlers.onDone();
          break;
        }
        buffer += decoder.decode(value, { stream: true });
        const parsed = parseAndEmit(buffer);
        buffer = parsed.rest;

        for (const block of parsed.blocks) {
          const lines = block.split('\n');
          const dataLines = lines
            .map((line) => line.trim())
            .filter((line) => line.startsWith('data:'))
            .map((line) => line.slice(5).trim());
          if (!dataLines.length) continue;
          const dataText = dataLines.join('\n');

          if (dataText === '[DONE]') {
            handlers.onDone();
            controller.abort();
            return;
          }
          try {
            handlers.onEvent(JSON.parse(dataText) as AgentLoopEvent);
          } catch {
            // 非 JSON 片段忽略，避免流式中间态影响
          }
        }
      }
    })
    .catch((error: unknown) => {
      if ((error as { name?: string }).name === 'AbortError') return;
      handlers.onError(error instanceof Error ? error : new Error('SSE 连接异常'));
    });

  return {
    close: () => controller.abort(),
  };
}
