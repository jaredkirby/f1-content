import { requireChatGPTUser } from "../chatgpt-auth";
import operation from "../data/credential-operation.json";
import KeyEntry from "./key-entry";

export const dynamic = "force-dynamic";
export default async function Page() {
  await requireChatGPTUser("/connect");
  return <KeyEntry operation={operation} />;
}
