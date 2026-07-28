import { expect, test, type Page } from "@playwright/test";

/**
 * The six core journeys, end to end against a real backend.
 *
 * Running order matters: journey 1 indexes the document that journeys 2 and 3
 * retrieve. Playwright runs a file's tests in declaration order with
 * `workers: 1`, and the backend is a single shared workspace, so this file is
 * one continuous session rather than six independent tests.
 *
 * Assertions target what a user sees. Where a stub provider's exact wording
 * would be the only thing under test, the assertion checks the structure it
 * proves instead (an agent badge, a citation, a status change).
 */

const DOC_NAME = "vacation-policy.txt";
const DOC_TEXT = [
  "Vacation policy.",
  "Full-time employees receive twenty vacation days per year.",
  "Unused vacation days expire at the end of the calendar year.",
].join(" ");

async function uploadDocument(page: Page): Promise<void> {
  await page.goto("/documents");
  await page.locator('input[type="file"]').setInputFiles({
    name: DOC_NAME,
    mimeType: "text/plain",
    buffer: Buffer.from(DOC_TEXT),
  });
}

/**
 * Send a message on the agents page and wait for the specialist's reply.
 *
 * Waiting on the reply is load-bearing, not politeness: the chat empty state
 * suggests prompts like "Draft a project plan…", so a loose text assertion
 * matches page furniture instantly and the test races on to the next page
 * before the agent has written anything. The agent badge only exists on a
 * delivered turn, which makes it the honest signal that the run finished.
 */
async function askAgents(page: Page, message: string): Promise<string> {
  await page.getByPlaceholder("Message the AI team…").fill(message);
  await page.keyboard.press("Enter");

  const badge = page.getByTestId("agent-badge").last();
  await expect(badge).toBeVisible({ timeout: 60_000 });
  return ((await badge.textContent()) ?? "").trim();
}

test.describe("AutoPilot AI core journeys", () => {
  test("1 · a document uploads and reaches Indexed", async ({ page }) => {
    await uploadDocument(page);

    const row = page.getByText(DOC_NAME).first();
    await expect(row).toBeVisible();

    // Ingestion is event-driven and asynchronous: the row appears as
    // uploaded/processing and flips to Indexed once chunks are embedded.
    await expect(page.getByText("Indexed").first()).toBeVisible({
      timeout: 30_000,
    });
  });

  test("2 · knowledge search returns the indexed document", async ({ page }) => {
    await page.goto("/knowledge");

    await page.getByPlaceholder("Search your knowledge base…").fill("vacation days");
    // `exact` matters: the sidebar and topbar both carry a "Search… ⌘K" button.
    await page.getByRole("button", { name: "Search", exact: true }).click();

    // The citation carries the source filename, which is the real proof that
    // retrieval reached the document indexed in journey 1.
    await expect(page.getByText(DOC_NAME).first()).toBeVisible({ timeout: 30_000 });
  });

  test("3 · the assistant answers with a citation", async ({ page }) => {
    await page.goto("/assistant");

    await page
      .getByPlaceholder("Ask a question about your documents…")
      .fill("how many vacation days do we get?");
    await page.keyboard.press("Enter");

    // The stub cites [1] only on the grounded prompt, so a visible citation
    // means retrieval ran and the answer was built from context.
    await expect(page.getByText("[1]").first()).toBeVisible({ timeout: 30_000 });
  });

  test("4 · the supervisor routes a message to a specialist", async ({ page }) => {
    await page.goto("/agents");

    // Small talk routes to `general`. Asserting the routing badge rather than
    // the reply keeps this about routing, not about what a stub happened to say.
    expect(await askAgents(page, "hey there!")).toBe("general");
  });

  test("5 · the planner turns a goal into tasks", async ({ page }) => {
    await page.goto("/agents");

    const agent = await askAgents(
      page,
      "plan the launch of our new onboarding guide",
    );
    expect(agent).toBe("planner");

    // The planner's real value is the rows it writes, so check the Tasks page,
    // not the chat reply.
    await page.goto("/tasks");
    await expect(page.getByText("Clarify the goal").first()).toBeVisible({
      timeout: 30_000,
    });
  });

  test("6 · an approval pauses a run and resumes it", async ({ page }) => {
    await page.goto("/agents");

    await page.getByRole("checkbox").first().check();
    await page.getByPlaceholder("Message the AI team…").fill("hello with approval");
    await page.keyboard.press("Enter");

    // The run suspends at the gate, so the turn is delivered as a draft rather
    // than an answer. Wait for that before leaving the page: the approvals list
    // is fetched on load and would otherwise render before the row exists.
    await expect(page.getByText("Awaiting approval").first()).toBeVisible({
      timeout: 60_000,
    });

    await page.goto("/approvals");
    const approveButton = page.getByRole("button", { name: /Approve/ }).first();
    await expect(approveButton).toBeVisible({ timeout: 30_000 });

    await approveButton.click();

    // Approving resumes the run from its checkpoint and empties the queue.
    await expect(page.getByText("You’re all caught up")).toBeVisible({
      timeout: 30_000,
    });
  });
});
