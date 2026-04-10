import "server-only";

import neo4j from "neo4j-driver";
import type { ArtifactKind } from "@/components/chat/artifact";
import type { VisibilityType } from "@/components/chat/visibility-selector";
import { ChatbotError } from "../errors";
import { generateUUID } from "../utils";
import { getDriver } from "./driver";
import type {
  Chat,
  DBMessage,
  Document,
  Suggestion,
  User,
  Vote,
} from "./schema";
import { generateHashedPassword } from "./utils";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function toDate(val: unknown): Date {
  if (val instanceof Date) return val;
  if (typeof val === "string" || typeof val === "number") return new Date(val);
  // neo4j DateTime object
  if (val && typeof val === "object" && "toStandardDate" in val) {
    return (val as { toStandardDate: () => Date }).toStandardDate();
  }
  return new Date();
}

function toJson(val: unknown): unknown {
  if (typeof val === "string") {
    try {
      return JSON.parse(val);
    } catch {
      return val;
    }
  }
  return val;
}

// ---------------------------------------------------------------------------
// User queries
// ---------------------------------------------------------------------------

export async function getUser(email: string): Promise<User[]> {
  const driver = getDriver();
  const session = driver.session();
  try {
    const result = await session.run(
      `MATCH (u:User {email: $email}) RETURN u`,
      { email }
    );
    return result.records.map((r) => {
      const props = r.get("u").properties;
      return {
        ...props,
        createdAt: toDate(props.createdAt),
        updatedAt: toDate(props.updatedAt),
        emailVerified: props.emailVerified ?? false,
        isAnonymous: props.isAnonymous ?? false,
      } as User;
    });
  } catch (_error) {
    throw new ChatbotError(
      "bad_request:database",
      "Failed to get user by email"
    );
  } finally {
    await session.close();
  }
}

export async function createUser(email: string, password: string) {
  const hashedPassword = generateHashedPassword(password);
  const driver = getDriver();
  const session = driver.session();
  try {
    await session.run(
      `CREATE (u:User {
        id: $id,
        email: $email,
        password: $password,
        name: null,
        emailVerified: false,
        image: null,
        isAnonymous: false,
        createdAt: datetime(),
        updatedAt: datetime()
      })`,
      { id: generateUUID(), email, password: hashedPassword }
    );
  } catch (_error) {
    throw new ChatbotError("bad_request:database", "Failed to create user");
  } finally {
    await session.close();
  }
}

export async function createGuestUser() {
  const email = `guest-${Date.now()}`;
  const password = generateHashedPassword(generateUUID());
  const id = generateUUID();
  const driver = getDriver();
  const session = driver.session();
  try {
    const result = await session.run(
      `CREATE (u:User {
        id: $id,
        email: $email,
        password: $password,
        name: null,
        emailVerified: false,
        image: null,
        isAnonymous: true,
        createdAt: datetime(),
        updatedAt: datetime()
      })
      RETURN u.id AS id, u.email AS email`,
      { id, email, password }
    );
    return result.records.map((r) => ({
      id: r.get("id") as string,
      email: r.get("email") as string,
    }));
  } catch (_error) {
    throw new ChatbotError(
      "bad_request:database",
      "Failed to create guest user"
    );
  } finally {
    await session.close();
  }
}

// ---------------------------------------------------------------------------
// Chat queries
// ---------------------------------------------------------------------------

export async function saveChat({
  id,
  userId,
  title,
  visibility,
}: {
  id: string;
  userId: string;
  title: string;
  visibility: VisibilityType;
}) {
  const driver = getDriver();
  const session = driver.session();
  try {
    await session.run(
      `MATCH (u:User {id: $userId})
       CREATE (c:Chat {
         id: $id,
         createdAt: datetime(),
         title: $title,
         userId: $userId,
         visibility: $visibility
       })
       CREATE (u)-[:OWNS_CHAT]->(c)`,
      { id, userId, title, visibility }
    );
  } catch (_error) {
    throw new ChatbotError("bad_request:database", "Failed to save chat");
  } finally {
    await session.close();
  }
}

export async function deleteChatById({ id }: { id: string }) {
  const driver = getDriver();
  const session = driver.session();
  try {
    const result = await session.run(
      `MATCH (c:Chat {id: $id})
       OPTIONAL MATCH (c)<-[:IN_CHAT]-(m:Message)
       OPTIONAL MATCH (m)<-[:VOTES_ON]-(v:Vote)
       OPTIONAL MATCH (c)<-[:STREAM_OF]-(s:Stream)
       DETACH DELETE v, m, s
       WITH c, c {.*} AS chatProps
       DETACH DELETE c
       RETURN chatProps`,
      { id }
    );
    if (result.records.length === 0) return null;
    const props = result.records[0].get("chatProps");
    return { ...props, createdAt: toDate(props.createdAt) } as Chat;
  } catch (_error) {
    throw new ChatbotError(
      "bad_request:database",
      "Failed to delete chat by id"
    );
  } finally {
    await session.close();
  }
}

export async function deleteAllChatsByUserId({
  userId,
}: {
  userId: string;
}) {
  const driver = getDriver();
  const session = driver.session();
  try {
    const result = await session.run(
      `MATCH (c:Chat {userId: $userId})
       OPTIONAL MATCH (c)<-[:IN_CHAT]-(m:Message)
       OPTIONAL MATCH (m)<-[:VOTES_ON]-(v:Vote)
       OPTIONAL MATCH (c)<-[:STREAM_OF]-(s:Stream)
       DETACH DELETE v, m, s
       WITH c
       DETACH DELETE c
       RETURN count(c) AS deletedCount`,
      { userId }
    );
    const count = result.records[0]?.get("deletedCount");
    return {
      deletedCount:
        typeof count === "object" && count !== null && "toNumber" in count
          ? (count as { toNumber: () => number }).toNumber()
          : Number(count ?? 0),
    };
  } catch (_error) {
    throw new ChatbotError(
      "bad_request:database",
      "Failed to delete all chats by user id"
    );
  } finally {
    await session.close();
  }
}

export async function getChatsByUserId({
  id,
  limit,
  startingAfter,
  endingBefore,
}: {
  id: string;
  limit: number;
  startingAfter: string | null;
  endingBefore: string | null;
}) {
  const driver = getDriver();
  const session = driver.session();
  try {
    const extendedLimit = neo4j.int(limit + 1);
    let cypher: string;
    let params: Record<string, unknown> = { userId: id, limit: extendedLimit };

    if (startingAfter) {
      cypher = `
        MATCH (ref:Chat {id: $ref})
        WITH ref.createdAt AS refDate
        MATCH (c:Chat {userId: $userId})
        WHERE c.createdAt > refDate
        RETURN c ORDER BY c.createdAt DESC LIMIT $limit`;
      params = { ...params, ref: startingAfter };
    } else if (endingBefore) {
      cypher = `
        MATCH (ref:Chat {id: $ref})
        WITH ref.createdAt AS refDate
        MATCH (c:Chat {userId: $userId})
        WHERE c.createdAt < refDate
        RETURN c ORDER BY c.createdAt DESC LIMIT $limit`;
      params = { ...params, ref: endingBefore };
    } else {
      cypher = `
        MATCH (c:Chat {userId: $userId})
        RETURN c ORDER BY c.createdAt DESC LIMIT $limit`;
    }

    const result = await session.run(cypher, params);
    const filteredChats: Chat[] = result.records.map((r) => {
      const props = r.get("c").properties;
      return { ...props, createdAt: toDate(props.createdAt) } as Chat;
    });

    const hasMore = filteredChats.length > limit;
    return {
      chats: hasMore ? filteredChats.slice(0, limit) : filteredChats,
      hasMore,
    };
  } catch (_error) {
    throw new ChatbotError(
      "bad_request:database",
      "Failed to get chats by user id"
    );
  } finally {
    await session.close();
  }
}

export async function getChatById({ id }: { id: string }) {
  const driver = getDriver();
  const session = driver.session();
  try {
    const result = await session.run(
      `MATCH (c:Chat {id: $id}) RETURN c LIMIT 1`,
      { id }
    );
    if (result.records.length === 0) return null;
    const props = result.records[0].get("c").properties;
    return { ...props, createdAt: toDate(props.createdAt) } as Chat;
  } catch (_error) {
    throw new ChatbotError("bad_request:database", "Failed to get chat by id");
  } finally {
    await session.close();
  }
}

// ---------------------------------------------------------------------------
// Message queries
// ---------------------------------------------------------------------------

export async function saveMessages({
  messages,
}: {
  messages: DBMessage[];
}) {
  const driver = getDriver();
  const session = driver.session();
  try {
    for (const msg of messages) {
      await session.run(
        `MATCH (c:Chat {id: $chatId})
         CREATE (m:Message {
           id: $id,
           chatId: $chatId,
           role: $role,
           parts: $parts,
           attachments: $attachments,
           createdAt: datetime($createdAt)
         })
         CREATE (m)-[:IN_CHAT]->(c)`,
        {
          id: msg.id,
          chatId: msg.chatId,
          role: msg.role,
          parts: JSON.stringify(msg.parts),
          attachments: JSON.stringify(msg.attachments),
          createdAt: new Date(msg.createdAt).toISOString(),
        }
      );
    }
  } catch (_error) {
    throw new ChatbotError("bad_request:database", "Failed to save messages");
  } finally {
    await session.close();
  }
}

export async function updateMessage({
  id,
  parts,
}: {
  id: string;
  parts: DBMessage["parts"];
}) {
  const driver = getDriver();
  const session = driver.session();
  try {
    await session.run(
      `MATCH (m:Message {id: $id}) SET m.parts = $parts`,
      { id, parts: JSON.stringify(parts) }
    );
  } catch (_error) {
    throw new ChatbotError("bad_request:database", "Failed to update message");
  } finally {
    await session.close();
  }
}

export async function getMessagesByChatId({ id }: { id: string }) {
  const driver = getDriver();
  const session = driver.session();
  try {
    const result = await session.run(
      `MATCH (m:Message {chatId: $id})
       RETURN m ORDER BY m.createdAt ASC`,
      { id }
    );
    return result.records.map((r) => {
      const props = r.get("m").properties;
      return {
        ...props,
        createdAt: toDate(props.createdAt),
        parts: toJson(props.parts),
        attachments: toJson(props.attachments),
      } as DBMessage;
    });
  } catch (_error) {
    throw new ChatbotError(
      "bad_request:database",
      "Failed to get messages by chat id"
    );
  } finally {
    await session.close();
  }
}

export async function getMessageById({ id }: { id: string }) {
  const driver = getDriver();
  const session = driver.session();
  try {
    const result = await session.run(
      `MATCH (m:Message {id: $id}) RETURN m`,
      { id }
    );
    return result.records.map((r) => {
      const props = r.get("m").properties;
      return {
        ...props,
        createdAt: toDate(props.createdAt),
        parts: toJson(props.parts),
        attachments: toJson(props.attachments),
      } as DBMessage;
    });
  } catch (_error) {
    throw new ChatbotError(
      "bad_request:database",
      "Failed to get message by id"
    );
  } finally {
    await session.close();
  }
}

export async function deleteMessagesByChatIdAfterTimestamp({
  chatId,
  timestamp,
}: {
  chatId: string;
  timestamp: Date;
}) {
  const driver = getDriver();
  const session = driver.session();
  try {
    // Delete votes on those messages first
    await session.run(
      `MATCH (m:Message {chatId: $chatId})
       WHERE m.createdAt >= datetime($ts)
       OPTIONAL MATCH (m)<-[:VOTES_ON]-(v:Vote)
       DETACH DELETE v`,
      { chatId, ts: timestamp.toISOString() }
    );
    // Then delete the messages
    await session.run(
      `MATCH (m:Message {chatId: $chatId})
       WHERE m.createdAt >= datetime($ts)
       DETACH DELETE m`,
      { chatId, ts: timestamp.toISOString() }
    );
  } catch (_error) {
    throw new ChatbotError(
      "bad_request:database",
      "Failed to delete messages by chat id after timestamp"
    );
  } finally {
    await session.close();
  }
}

// ---------------------------------------------------------------------------
// Vote queries
// ---------------------------------------------------------------------------

export async function voteMessage({
  chatId,
  messageId,
  type,
}: {
  chatId: string;
  messageId: string;
  type: "up" | "down";
}) {
  const driver = getDriver();
  const session = driver.session();
  try {
    await session.run(
      `MERGE (v:Vote {chatId: $chatId, messageId: $messageId})
       ON CREATE SET v.isUpvoted = $isUpvoted
       ON MATCH SET v.isUpvoted = $isUpvoted
       WITH v
       MATCH (m:Message {id: $messageId})
       MERGE (v)-[:VOTES_ON]->(m)`,
      { chatId, messageId, isUpvoted: type === "up" }
    );
  } catch (_error) {
    throw new ChatbotError("bad_request:database", "Failed to vote message");
  } finally {
    await session.close();
  }
}

export async function getVotesByChatId({ id }: { id: string }) {
  const driver = getDriver();
  const session = driver.session();
  try {
    const result = await session.run(
      `MATCH (v:Vote {chatId: $id}) RETURN v`,
      { id }
    );
    return result.records.map((r) => r.get("v").properties as Vote);
  } catch (_error) {
    throw new ChatbotError(
      "bad_request:database",
      "Failed to get votes by chat id"
    );
  } finally {
    await session.close();
  }
}

// ---------------------------------------------------------------------------
// Document queries
// ---------------------------------------------------------------------------

export async function saveDocument({
  id,
  title,
  kind,
  content,
  userId,
}: {
  id: string;
  title: string;
  kind: ArtifactKind;
  content: string;
  userId: string;
}) {
  const driver = getDriver();
  const session = driver.session();
  try {
    const result = await session.run(
      `CREATE (d:Document {
        id: $id,
        title: $title,
        kind: $kind,
        content: $content,
        userId: $userId,
        createdAt: datetime()
      })
      RETURN d`,
      { id, title, kind, content, userId }
    );
    return result.records.map((r) => {
      const props = r.get("d").properties;
      return { ...props, createdAt: toDate(props.createdAt) } as Document;
    });
  } catch (_error) {
    throw new ChatbotError("bad_request:database", "Failed to save document");
  } finally {
    await session.close();
  }
}

export async function updateDocumentContent({
  id,
  content,
}: {
  id: string;
  content: string;
}) {
  const driver = getDriver();
  const session = driver.session();
  try {
    // Get the latest version
    const latest = await session.run(
      `MATCH (d:Document {id: $id})
       RETURN d ORDER BY d.createdAt DESC LIMIT 1`,
      { id }
    );
    if (latest.records.length === 0) {
      throw new ChatbotError("not_found:database", "Document not found");
    }
    const props = latest.records[0].get("d").properties;
    const createdAt = props.createdAt;

    const result = await session.run(
      `MATCH (d:Document {id: $id})
       WHERE d.createdAt = $createdAt
       SET d.content = $content
       RETURN d`,
      { id, content, createdAt }
    );
    return result.records.map((r) => {
      const p = r.get("d").properties;
      return { ...p, createdAt: toDate(p.createdAt) } as Document;
    });
  } catch (_error) {
    if (_error instanceof ChatbotError) throw _error;
    throw new ChatbotError(
      "bad_request:database",
      "Failed to update document content"
    );
  } finally {
    await session.close();
  }
}

export async function getDocumentsById({ id }: { id: string }) {
  const driver = getDriver();
  const session = driver.session();
  try {
    const result = await session.run(
      `MATCH (d:Document {id: $id})
       RETURN d ORDER BY d.createdAt ASC`,
      { id }
    );
    return result.records.map((r) => {
      const props = r.get("d").properties;
      return { ...props, createdAt: toDate(props.createdAt) } as Document;
    });
  } catch (_error) {
    throw new ChatbotError(
      "bad_request:database",
      "Failed to get documents by id"
    );
  } finally {
    await session.close();
  }
}

export async function getDocumentById({ id }: { id: string }) {
  const driver = getDriver();
  const session = driver.session();
  try {
    const result = await session.run(
      `MATCH (d:Document {id: $id})
       RETURN d ORDER BY d.createdAt DESC LIMIT 1`,
      { id }
    );
    if (result.records.length === 0) return undefined;
    const props = result.records[0].get("d").properties;
    return { ...props, createdAt: toDate(props.createdAt) } as Document;
  } catch (_error) {
    throw new ChatbotError(
      "bad_request:database",
      "Failed to get document by id"
    );
  } finally {
    await session.close();
  }
}

export async function deleteDocumentsByIdAfterTimestamp({
  id,
  timestamp,
}: {
  id: string;
  timestamp: Date;
}) {
  const driver = getDriver();
  const session = driver.session();
  try {
    // Delete related suggestions first
    await session.run(
      `MATCH (s:Suggestion {documentId: $id})
       WHERE s.documentCreatedAt > datetime($ts)
       DETACH DELETE s`,
      { id, ts: timestamp.toISOString() }
    );
    const result = await session.run(
      `MATCH (d:Document {id: $id})
       WHERE d.createdAt > datetime($ts)
       WITH d, d {.*} AS props
       DETACH DELETE d
       RETURN props`,
      { id, ts: timestamp.toISOString() }
    );
    return result.records.map((r) => {
      const props = r.get("props");
      return { ...props, createdAt: toDate(props.createdAt) } as Document;
    });
  } catch (_error) {
    throw new ChatbotError(
      "bad_request:database",
      "Failed to delete documents by id after timestamp"
    );
  } finally {
    await session.close();
  }
}

// ---------------------------------------------------------------------------
// Suggestion queries
// ---------------------------------------------------------------------------

export async function saveSuggestions({
  suggestions,
}: {
  suggestions: Suggestion[];
}) {
  const driver = getDriver();
  const session = driver.session();
  try {
    for (const s of suggestions) {
      await session.run(
        `CREATE (sg:Suggestion {
          id: $id,
          documentId: $documentId,
          documentCreatedAt: datetime($documentCreatedAt),
          originalText: $originalText,
          suggestedText: $suggestedText,
          description: $description,
          isResolved: $isResolved,
          userId: $userId,
          createdAt: datetime($createdAt)
        })`,
        {
          id: s.id,
          documentId: s.documentId,
          documentCreatedAt: new Date(s.documentCreatedAt).toISOString(),
          originalText: s.originalText,
          suggestedText: s.suggestedText,
          description: s.description,
          isResolved: s.isResolved,
          userId: s.userId,
          createdAt: new Date(s.createdAt).toISOString(),
        }
      );
    }
  } catch (_error) {
    throw new ChatbotError(
      "bad_request:database",
      "Failed to save suggestions"
    );
  } finally {
    await session.close();
  }
}

export async function getSuggestionsByDocumentId({
  documentId,
}: {
  documentId: string;
}) {
  const driver = getDriver();
  const session = driver.session();
  try {
    const result = await session.run(
      `MATCH (s:Suggestion {documentId: $documentId}) RETURN s`,
      { documentId }
    );
    return result.records.map((r) => {
      const props = r.get("s").properties;
      return {
        ...props,
        createdAt: toDate(props.createdAt),
        documentCreatedAt: toDate(props.documentCreatedAt),
      } as Suggestion;
    });
  } catch (_error) {
    throw new ChatbotError(
      "bad_request:database",
      "Failed to get suggestions by document id"
    );
  } finally {
    await session.close();
  }
}

// ---------------------------------------------------------------------------
// Chat metadata
// ---------------------------------------------------------------------------

export async function updateChatVisibilityById({
  chatId,
  visibility,
}: {
  chatId: string;
  visibility: "private" | "public";
}) {
  const driver = getDriver();
  const session = driver.session();
  try {
    await session.run(
      `MATCH (c:Chat {id: $chatId}) SET c.visibility = $visibility`,
      { chatId, visibility }
    );
  } catch (_error) {
    throw new ChatbotError(
      "bad_request:database",
      "Failed to update chat visibility by id"
    );
  } finally {
    await session.close();
  }
}

export async function updateChatTitleById({
  chatId,
  title,
}: {
  chatId: string;
  title: string;
}) {
  const driver = getDriver();
  const session = driver.session();
  try {
    await session.run(
      `MATCH (c:Chat {id: $chatId}) SET c.title = $title`,
      { chatId, title }
    );
  } catch (_error) {
    // non-critical, matches original behaviour
    return;
  } finally {
    await session.close();
  }
}

// ---------------------------------------------------------------------------
// Message count (rate-limiting helper)
// ---------------------------------------------------------------------------

export async function getMessageCountByUserId({
  id,
  differenceInHours,
}: {
  id: string;
  differenceInHours: number;
}) {
  const driver = getDriver();
  const session = driver.session();
  try {
    const cutoff = new Date(
      Date.now() - differenceInHours * 60 * 60 * 1000
    ).toISOString();

    const result = await session.run(
      `MATCH (c:Chat {userId: $userId})<-[:IN_CHAT]-(m:Message)
       WHERE m.role = 'user' AND m.createdAt >= datetime($cutoff)
       RETURN count(m) AS cnt`,
      { userId: id, cutoff }
    );
    const cnt = result.records[0]?.get("cnt");
    if (cnt && typeof cnt === "object" && "toNumber" in cnt) {
      return (cnt as { toNumber: () => number }).toNumber();
    }
    return Number(cnt ?? 0);
  } catch (_error) {
    throw new ChatbotError(
      "bad_request:database",
      "Failed to get message count by user id"
    );
  } finally {
    await session.close();
  }
}

// ---------------------------------------------------------------------------
// Stream queries (resumable streams)
// ---------------------------------------------------------------------------

export async function createStreamId({
  streamId,
  chatId,
}: {
  streamId: string;
  chatId: string;
}) {
  const driver = getDriver();
  const session = driver.session();
  try {
    await session.run(
      `MATCH (c:Chat {id: $chatId})
       CREATE (s:Stream {id: $streamId, chatId: $chatId, createdAt: datetime()})
       CREATE (s)-[:STREAM_OF]->(c)`,
      { streamId, chatId }
    );
  } catch (_error) {
    throw new ChatbotError(
      "bad_request:database",
      "Failed to create stream id"
    );
  } finally {
    await session.close();
  }
}

export async function getStreamIdsByChatId({
  chatId,
}: {
  chatId: string;
}) {
  const driver = getDriver();
  const session = driver.session();
  try {
    const result = await session.run(
      `MATCH (s:Stream {chatId: $chatId})
       RETURN s.id AS id ORDER BY s.createdAt ASC`,
      { chatId }
    );
    return result.records.map((r) => r.get("id") as string);
  } catch (_error) {
    throw new ChatbotError(
      "bad_request:database",
      "Failed to get stream ids by chat id"
    );
  } finally {
    await session.close();
  }
}
