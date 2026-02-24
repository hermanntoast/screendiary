import { create } from "zustand";
import { streamAiChat, type ChatMessage } from "./api/client";

interface ChatState {
  messages: ChatMessage[];
  input: string;
  streaming: boolean;

  setInput: (input: string) => void;
  sendMessage: () => Promise<void>;
  clearChat: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  input: "",
  streaming: false,

  setInput: (input: string) => set({ input }),

  sendMessage: async () => {
    const { input, messages, streaming } = get();
    const query = input.trim();
    if (!query || streaming) return;

    const userMsg: ChatMessage = { role: "user", content: query };
    const history = [...messages];
    const assistantMsg: ChatMessage = { role: "assistant", content: "" };

    set({
      messages: [...messages, userMsg, assistantMsg],
      input: "",
      streaming: true,
    });

    await streamAiChat(
      query,
      history,
      (token) => {
        const msgs = get().messages;
        const last = msgs[msgs.length - 1]!;
        set({
          messages: [
            ...msgs.slice(0, -1),
            { ...last, content: last.content + token },
          ],
        });
      },
      () => set({ streaming: false }),
      (err) => {
        const msgs = get().messages;
        const last = msgs[msgs.length - 1]!;
        set({
          messages: [
            ...msgs.slice(0, -1),
            { ...last, content: last.content || `Fehler: ${err}` },
          ],
          streaming: false,
        });
      },
    );
  },

  clearChat: () => set({ messages: [], input: "", streaming: false }),
}));
