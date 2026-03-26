import os
import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.monitor import Monitor
from farm_env import FarmEnv


class SurvivalTracker(BaseCallback):
    """Tracks survival episodes and prints periodic summaries."""

    def __init__(self, verbose=1):
        super().__init__(verbose)
        self.episodes = 0
        self.ep_rewards = []
        self.ep_lengths = []

    def _on_step(self):
        # Check for episode end via infos
        infos = self.locals.get("infos", [])
        for info in infos:
            if "episode" in info:
                self.episodes += 1
                self.ep_rewards.append(info["episode"]["r"])
                self.ep_lengths.append(info["episode"]["l"])
                
                if self.episodes % 50 == 0:
                    recent_r = self.ep_rewards[-50:]
                    recent_l = self.ep_lengths[-50:]
                    avg_r = sum(recent_r) / len(recent_r)
                    avg_l = sum(recent_l) / len(recent_l)
                    print(
                        f"  ► ep {self.episodes:>5d} | avg50_reward={avg_r:>7.1f} | avg50_length={avg_l:>6.1f}"
                    )
        return True


def main():
    xml_path = os.path.join(os.getcwd(), "farm_field.xml")
    
    # Create environment with visualization enabled and wrap in Monitor
    env = FarmEnv(xml_path, render_mode="human")
    env = Monitor(env)

    model = PPO(
        "MlpPolicy",
        env,
        learning_rate=3e-4,
        n_steps=2048,
        batch_size=64,
        n_epochs=10,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.05,  # Increased to encourage steering exploration
        vf_coef=0.5,
        max_grad_norm=0.5,
        verbose=1,
        policy_kwargs=dict(net_arch=[128, 128]),
        device="cpu",
    )

    tracker = SurvivalTracker()
    total_timesteps = 1_000_000

    print(f"Training PPO for {total_timesteps:,} steps on FarmEnv (Obstacle Avoidance)...")
    try:
        model.learn(total_timesteps=total_timesteps, callback=tracker)
    except KeyboardInterrupt:
        print("\nTraining interrupted by user. Saving current progress...")
    finally:
        model.save("farm_ppo_sb3")
        print("\nDone training!")
        print("Model saved to farm_ppo_sb3.zip")


if __name__ == "__main__":
    main()
