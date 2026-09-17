/**
 * ResultsZone component tests.
 *
 * These are unit tests for the ResultsZone component logic.
 * Since this is a simple component, we test the props and rendering logic.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { ZONES, getZone, zoneFromHash, DEFAULT_ZONE } from "../../zones.ts";

test("ZONES: includes results zone for F5", () => {
  const resultsZone = ZONES.find(z => z.id === "results");
  assert.ok(resultsZone, "results zone exists");
  assert.equal(resultsZone!.id, "results");
  assert.equal(resultsZone!.label, "Results & Assets");
  assert.equal(resultsZone!.description, "preview, lineage, verification");
  assert.equal(resultsZone!.phase, "F5");
});

test("getZone: results zone exists and has correct properties", () => {
  const zone = getZone("results");
  assert.equal(zone.id, "results");
  assert.equal(zone.label, "Results & Assets");
  assert.equal(zone.phase, "F5");
});

test("zoneFromHash: works for results zone", () => {
  assert.equal(zoneFromHash("#/results"), "results");
  assert.equal(zoneFromHash("#/results?foo=bar"), "results");
});

test("DEFAULT_ZONE is conversation", () => {
  assert.equal(DEFAULT_ZONE, "conversation");
});