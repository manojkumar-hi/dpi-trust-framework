import "dotenv/config";
import express from "express";
import credentialsRouter, {
  FabricOperationError,
} from "./routes/credentials.js";
import delegationsRouter from "./routes/delegations.js";
import { closeFabricConnection } from "./fabric-client.js";
import { config } from "./config.js";

const app = express();

app.use(express.json());

app.get("/health", (_request, response) => {
  response.json({ success: true, result: { status: "ok" }, transaction_id: null });
});

app.use("/internal/credentials", credentialsRouter);
app.use("/internal/delegations", delegationsRouter);


app.use((error, _request, response, _next) => {
  const statusCode = error.statusCode ?? (
    error instanceof FabricOperationError ? 503 : 500
  );
  const type = error.type ?? error.name ?? "InternalServerError";

  response.status(statusCode).json({
    success: false,
    error: {
      message: error.message,
      type,
    },
  });
});

const server = app.listen(config.port || 8081, () => {
  console.log(`Fabric Gateway adapter listening on port ${config.port || 8081}`);
});

function shutdown(signal) {
  console.log(`${signal} received; shutting down`);
  server.close(() => {
    closeFabricConnection();
    process.exit(0);
  });
}

process.once("SIGINT", () => shutdown("SIGINT"));
process.once("SIGTERM", () => shutdown("SIGTERM"));

export { app, server };
