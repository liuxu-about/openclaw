type ComputerAction =
  | { type: "press"; id: string }
  | { type: "focus"; id: string }
  | { type: "set_value"; id: string; text: string }
  | { type: "append_text"; id: string; text: string }
  | { type: "select"; id: string; value?: string }
  | { type: "scroll"; id?: string; direction: "up" | "down" | "left" | "right"; amount?: number }
  | { type: "key"; keys: string[] }
  | { type: "wait"; ms: number }
  | { type: "vision_click"; x: number; y: number; reason: string };

type ComputerObserveParams = {
  target_app?: string;
  target_window?: string;
  include_screenshot?: boolean;
  max_nodes?: number;
};

type ComputerActParams = {
  observation_id: string;
  actions: ComputerAction[];
};

type ComputerUseTaskParams = {
  task: string;
  target_app?: string;
  approval_mode?: "strict" | "normal";
  allow_vision_fallback?: boolean;
};

class ComputerNodeClient {
  async request(method: string, params: Record<string, unknown>): Promise<unknown> {
    return {
      ok: false,
      method,
      params,
      message:
        "Prototype only. Wire this client to computer-use/node/server.py over stdio or a local socket.",
    };
  }
}

const nodeClient = new ComputerNodeClient();

function isSensitiveAction(action: ComputerAction): boolean {
  if (action.type === "vision_click") {
    const reason = action.reason.toLowerCase();
    return ["payment", "purchase", "delete", "password", "token", "secret", "system settings"].some((word) =>
      reason.includes(word),
    );
  }

  if (action.type === "set_value" || action.type === "append_text") {
    const text = action.text.toLowerCase();
    return ["password", "token", "secret", "recovery code"].some((word) => text.includes(word));
  }

  return false;
}

async function checkPolicy(actions: ComputerAction[]): Promise<{ requiresApproval: boolean; reasons: string[] }> {
  const reasons: string[] = [];
  for (const action of actions) {
    if (isSensitiveAction(action)) {
      reasons.push(`Sensitive computer action requires approval: ${action.type}`);
    }
  }
  return { requiresApproval: reasons.length > 0, reasons };
}

export async function computerObserve(params: ComputerObserveParams): Promise<unknown> {
  return nodeClient.request("computer.observe", params as Record<string, unknown>);
}

export async function computerAct(params: ComputerActParams): Promise<unknown> {
  const decision = await checkPolicy(params.actions);
  if (decision.requiresApproval) {
    return {
      ok: false,
      requires_approval: true,
      approval_reasons: decision.reasons,
      message: "Approval UI is not wired in this prototype yet.",
    };
  }
  return nodeClient.request("computer.act", params as unknown as Record<string, unknown>);
}

export async function computerStop(): Promise<unknown> {
  return nodeClient.request("computer.stop", {});
}

export async function computerUseTask(params: ComputerUseTaskParams): Promise<unknown> {
  return {
    ok: false,
    message:
      "High level task runner is not implemented yet. The next step is an observe-act-verify loop that calls computerObserve and computerAct.",
    params,
  };
}

export function registerComputerUseTools(api: {
  registerTool?: (tool: unknown) => void;
}): void {
  if (!api.registerTool) {
    return;
  }

  api.registerTool({
    name: "computer_observe",
    description: "Observe an allowed macOS app using AX Tree first, with optional screenshot fallback.",
    execute: computerObserve,
  });

  api.registerTool({
    name: "computer_act",
    description: "Perform approved element level actions on the latest computer observation.",
    execute: computerAct,
  });

  api.registerTool({
    name: "computer_stop",
    description: "Stop the current computer-use session.",
    execute: computerStop,
  });

  api.registerTool({
    name: "computer_use",
    description: "Run a high level Computer Use task through observe, act, and verify steps.",
    execute: computerUseTask,
  });
}
