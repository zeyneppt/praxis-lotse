// Läuft mit dem eingebauten Test-Runner von Node (`npm test`), ohne zusätzliche Abhängigkeit.
// Von `tsc` ausgenommen, weil `@types/node` nicht installiert ist.
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  gesternInBerlin,
  MIN_TELEFON_ZIFFERN,
  TELEFON_MUSTER,
  telefonnummernTrennen,
  terminZeit,
} from "./format.ts";

function links(text: string): string[] {
  return telefonnummernTrennen(text).flatMap((teil) => (teil.telefon ? [teil.telefon] : []));
}

test("Notruf und Bereitschaftsdienst werden verlinkt", () => {
  assert.deepEqual(links("Bitte rufen Sie sofort den Notruf 112 an."), ["tel:112"]);
  assert.deepEqual(links("Bereitschaftsdienst 116117 oder 116 117"), ["tel:116117", "tel:116117"]);
});

test("Nummern mit Vorwahl werden verlinkt", () => {
  assert.deepEqual(links("Telefon: 0911 123456."), ["tel:0911123456"]);
  assert.deepEqual(links("Telefon 0911/123456 oder 0911-123456"), [
    "tel:0911123456",
    "tel:0911123456",
  ]);
  assert.deepEqual(links("TelefonSeelsorge: 0800 111 0 111 oder 0800 111 0 222."), [
    "tel:08001110111",
    "tel:08001110222",
  ]);
  assert.deepEqual(links("Mobil +49 170 1234567"), ["tel:+491701234567"]);
});

test("Zeiten, Bereiche und Daten werden nicht verlinkt", () => {
  for (const text of [
    "Sprechzeiten 08 - 12 Uhr",
    "Sprechzeiten 08:00-12:00 Uhr",
    "Mo–Fr 08:00 – 18:00",
    "Befund vom 03/2026",
    "am 01.03.2026",
    "Termin am 2026-10-28T08:30",
    "Raum 0812",
    "01067 Dresden",
    "Zimmer 1120",
  ]) {
    assert.deepEqual(links(text), [], text);
  }
});

test("Text bleibt beim Zerlegen vollständig erhalten", () => {
  const text = "Notruf 112, Praxis 0911 123456, Sprechzeit 08 - 12 Uhr.";
  assert.equal(
    telefonnummernTrennen(text)
      .map((teil) => teil.text)
      .join(""),
    text,
  );
});

test("Terminzeit wird in Europe/Berlin angezeigt", () => {
  assert.deepEqual(terminZeit("2026-10-28T08:30:00+01:00"), {
    datum: "Mittwoch, 28.10.2026",
    uhrzeit: "08:30 Uhr",
  });
  // 23:30 UTC ist in Berlin schon der nächste Tag.
  assert.equal(terminZeit("2026-10-27T23:30:00Z").datum, "Mittwoch, 28.10.2026");
});

test("spätestes Geburtsdatum ist gestern in Berlin", () => {
  assert.equal(gesternInBerlin(new Date("2026-10-27T10:00:00Z")), "2026-10-26");
  // 23:30 UTC am 27.10. ist in Berlin der 28.10.
  assert.equal(gesternInBerlin(new Date("2026-10-27T23:30:00Z")), "2026-10-27");
  assert.equal(gesternInBerlin(new Date("2026-03-01T12:00:00Z")), "2026-02-28");
});

test("Telefonmuster verlangt mindestens sechs Ziffern", () => {
  // Browser werten `pattern` verankert im v-Modus aus.
  const muster = new RegExp(`^(?:${TELEFON_MUSTER})$`, "v");
  assert.equal(MIN_TELEFON_ZIFFERN, 6);
  for (const gueltig of ["+49 170 0000000", "0911/123456", "0911-123456", "123456"]) {
    assert.ok(muster.test(gueltig), gueltig);
  }
  for (const ungueltig of ["++++++", "      ", "12345", "0911 12a456", "+49 1-2"]) {
    assert.ok(!muster.test(ungueltig), ungueltig);
  }
});
