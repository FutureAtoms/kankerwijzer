import { motion } from "framer-motion";

export const Greeting = () => {
  return (
    <div className="flex flex-col items-center px-4" key="overview">
      <motion.div
        animate={{ opacity: 1, y: 0 }}
        className="mb-2"
        initial={{ opacity: 0, y: 10 }}
        transition={{ delay: 0.2, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      >
        <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
          <circle
            cx="32"
            cy="32"
            r="30"
            stroke="oklch(0.65 0.2 160)"
            strokeWidth="2.5"
            opacity="0.3"
          />
          <circle
            cx="32"
            cy="32"
            r="22"
            stroke="oklch(0.65 0.2 160)"
            strokeWidth="2"
            opacity="0.5"
          />
          <circle
            cx="32"
            cy="32"
            r="14"
            fill="oklch(0.65 0.2 160)"
            opacity="0.1"
          />
          <path
            d="M32 22v12M28 30l4 4 4-4"
            stroke="oklch(0.65 0.2 160)"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle cx="32" cy="40" r="2" fill="oklch(0.65 0.2 160)" />
        </svg>
      </motion.div>
      <motion.div
        animate={{ opacity: 1, y: 0 }}
        className="text-center font-semibold text-2xl tracking-tight text-foreground md:text-3xl"
        initial={{ opacity: 0, y: 10 }}
        transition={{ delay: 0.35, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      >
        Welkom bij KankerWijzer
      </motion.div>
      <motion.div
        animate={{ opacity: 1, y: 0 }}
        className="mt-3 text-center text-muted-foreground/80 text-sm max-w-md"
        initial={{ opacity: 0, y: 10 }}
        transition={{ delay: 0.5, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      >
        Stel uw vraag over kanker en ontvang betrouwbare informatie gebaseerd op
        bronnen van IKNL, KWF en medische richtlijnen.
      </motion.div>
    </div>
  );
};
