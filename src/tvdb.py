import httpx
from src.console import console
from data.config import config

config = config


async def get_tvdb_episode_data(base_dir, token, tvdb_id, season, episode, api_key=None, retry_attempted=False, debug=False):
    console.print(f"[cyan]Fetching TVDb episode data for S{season}E{episode}...[/cyan]")

    url = f"https://api4.thetvdb.com/v4/series/{tvdb_id}/episodes/default"
    params = {
        "page": 1,
        "season": season,
        "episodeNumber": episode
    }
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {token}"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=headers, timeout=30.0)

            # Handle unauthorized responses
            if response.status_code == 401:
                # Only attempt a retry once to prevent infinite loops
                if api_key and not retry_attempted:
                    console.print("[yellow]Unauthorized access. Refreshing TVDb token...[/yellow]")
                    new_token = await get_tvdb_token(api_key, base_dir)
                    if new_token:
                        # Retry the request with the new token
                        return await get_tvdb_episode_data(
                            new_token, tvdb_id, season, episode, api_key, True
                        )
                    else:
                        console.print("[red]Failed to refresh TVDb token[/red]")
                        return None
                else:
                    console.print("[red]Unauthorized access to TVDb API[/red]")
                    return None

            response.raise_for_status()
            data = response.json()

            # Check for "Unauthorized" message in response body
            if data.get("message") == "Unauthorized":
                if api_key and not retry_attempted:
                    console.print("[yellow]Token invalid or expired. Refreshing TVDb token...[/yellow]")
                    new_token = await get_tvdb_token(api_key, base_dir)
                    if new_token:
                        return await get_tvdb_episode_data(
                            new_token, tvdb_id, season, episode, api_key, True
                        )
                    else:
                        console.print("[red]Failed to refresh TVDb token[/red]")
                        return None
                else:
                    console.print("[red]Unauthorized response from TVDb API[/red]")
                    return None

            if data.get("status") == "success" and data.get("data") and data["data"].get("episodes"):
                episode_data = data["data"]["episodes"][0]
                series_data = data["data"].get("series", {})

                result = {
                    "episode_name": episode_data.get("name", ""),
                    "overview": episode_data.get("overview", ""),
                    "season_number": episode_data.get("seasonNumber", season),
                    "episode_number": episode_data.get("number", episode),
                    "air_date": episode_data.get("aired", ""),
                    "season_name": episode_data.get("seasonName", ""),
                    "series_name": series_data.get("name", ""),
                    "series_overview": series_data.get("overview", ""),
                }

                if debug:
                    console.print(f"[green]Found episode: {result['season_name']} - S{result['season_number']}E{result['episode_number']} - {result['episode_name']}[/green] - {result['air_date']}")
                    console.print(f"[yellow]Overview: {result['overview']}")
                    console.print(f"[yellow]Series: {result['series_name']} - {result['series_overview']}[/yellow]")
                return result
            else:
                console.print(f"[yellow]No TVDB episode data found for S{season}E{episode}[/yellow]")
                return None

    except httpx.HTTPStatusError as e:
        console.print(f"[red]HTTP error occurred: {e.response.status_code} - {e.response.text}[/red]")
        return None
    except httpx.RequestError as e:
        console.print(f"[red]Request error occurred: {e}[/red]")
        return None
    except Exception as e:
        console.print(f"[red]Error fetching TVDb episode data: {e}[/red]")
        return None


async def get_tvdb_token(api_key, base_dir):
    console.print("[cyan]Authenticating with TVDb API...[/cyan]")

    url = "https://api4.thetvdb.com/v4/login"
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {
        "apikey": api_key,
        "pin": "string"  # Default value as specified in the example
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=30.0)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "success" and data.get("data") and data["data"].get("token"):
                token = data["data"]["token"]
                console.print("[green]Successfully authenticated with TVDb[/green]")
                console.print(f"[bold yellow]New TVDb token: {token}[/bold yellow]")

                # Update the token in the in-memory configuration
                config['DEFAULT']['tvdb_token'] = f'"{token}"'

                # Save the updated config to disk
                try:
                    # Get the config file path
                    config_path = f"{base_dir}/data/config.py"

                    # Read the current config file
                    with open(config_path, 'r', encoding='utf-8') as file:
                        config_data = file.read()

                    token_pattern = '"tvdb_token":'
                    if token_pattern in config_data:
                        # Find the line with tvdb_token
                        lines = config_data.splitlines()
                        for i, line in enumerate(lines):
                            if token_pattern in line:
                                # Split the line at the colon and keep everything before it
                                prefix = line.split(':', 1)[0]
                                # Create a new line with the updated token
                                lines[i] = f'{prefix}: "{token}",'
                                break

                        # Rejoin the lines and write back to the file
                        new_config_data = '\n'.join(lines)
                        with open(config_path, 'w', encoding='utf-8') as file:
                            file.write(new_config_data)

                        console.print(f"[bold green]TVDb token successfully saved to {config_path}[/bold green]")
                    else:
                        console.print("[yellow]Warning: Could not find tvdb_token in configuration file[/yellow]")
                        console.print("[yellow]The token will be used for this session only.[/yellow]")

                except Exception as e:
                    console.print(f"[yellow]Warning: Could not update TVDb token in configuration file: {e}[/yellow]")
                    console.print("[yellow]The token will be used for this session only.[/yellow]")

                return token
            else:
                console.print("[red]Failed to get TVDb token: Invalid response format[/red]")
                return None

    except httpx.HTTPStatusError as e:
        console.print(f"[red]HTTP error occurred during TVDb authentication: {e.response.status_code} - {e.response.text}[/red]")
        return None
    except httpx.RequestError as e:
        console.print(f"[red]Request error occurred during TVDb authentication: {e}[/red]")
        return None
    except Exception as e:
        console.print(f"[red]Error authenticating with TVDb: {e}[/red]")
        return None


async def get_tvdb_series_episodes(base_dir, token, tvdb_id, season, episode, api_key=None, retry_attempted=False, debug=False):
    console.print(f"[cyan]Fetching episode list for series ID {tvdb_id}...[/cyan]")

    url = f"https://api4.thetvdb.com/v4/series/{tvdb_id}/extended?meta=episodes&short=false"
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {token}"
    }

    all_episodes = []

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=30.0)

            # Handle unauthorized responses
            if response.status_code == 401:
                # Only attempt a retry once to prevent infinite loops
                if api_key and not retry_attempted:
                    console.print("[yellow]Unauthorized access. Refreshing TVDb token...[/yellow]")
                    new_token = await get_tvdb_token(api_key, base_dir)
                    if new_token:
                        # Retry the request with the new token
                        return await get_tvdb_series_episodes(
                            base_dir, new_token, tvdb_id, season, episode, api_key, True
                        )
                    else:
                        console.print("[red]Failed to refresh TVDb token[/red]")
                        return (season, episode)
                else:
                    console.print("[red]Unauthorized access to TVDb API[/red]")
                    return (season, episode)

            response.raise_for_status()
            data = response.json()

            # Check for "Unauthorized" message in response body
            if data.get("message") == "Unauthorized":
                if api_key and not retry_attempted:
                    console.print("[yellow]Token invalid or expired. Refreshing TVDb token...[/yellow]")
                    new_token = await get_tvdb_token(api_key, base_dir)
                    if new_token:
                        return await get_tvdb_series_episodes(
                            base_dir, new_token, tvdb_id, season, episode, api_key, True
                        )
                    else:
                        console.print("[red]Failed to refresh TVDb token[/red]")
                        return (season, episode)
                else:
                    console.print("[red]Unauthorized response from TVDb API[/red]")
                    return (season, episode)

            if data.get("status") == "success" and data.get("data"):
                episodes = data["data"].get("episodes", [])
                all_episodes = episodes

            if not all_episodes:
                console.print(f"[yellow]No episodes found for TVDB series ID {tvdb_id}[/yellow]")
                return (season, episode)

            if debug:
                console.print(f"[cyan]Looking for season {season} episode {episode} in series {tvdb_id}[/cyan]")

            # Process and organize episode data
            episodes_by_season = {}
            absolute_mapping = {}  # Map absolute numbers to season/episode

            # Sort by aired date first (if available)
            def get_aired_date(ep):
                aired = ep.get("aired")
                # Return default value if aired is None or not present
                if aired is None:
                    return "9999-99-99"
                return aired

            all_episodes.sort(key=get_aired_date)

            for ep in all_episodes:
                season_number = ep.get("seasonNumber")
                episode_number = ep.get("number")
                absolute_episode_count = ep.get("absoluteNumber")

                # Ensure season_number is valid and convert to int if needed
                if season_number is not None:
                    try:
                        season_number = int(season_number)
                    except (ValueError, TypeError):
                        console.print(f"[yellow]Invalid season number: {season_number}, skipping episode[/yellow]")
                        continue
                else:
                    console.print(f"[yellow]Missing season number for episode {ep.get('name', 'Unknown')}, skipping[/yellow]")
                    continue

                # Ensure episode_number is valid
                if episode_number is not None:
                    try:
                        episode_number = int(episode_number)
                    except (ValueError, TypeError):
                        console.print(f"[yellow]Invalid episode number: {episode_number}, skipping episode[/yellow]")
                        continue

                # Handle special seasons (e.g., season 0)
                is_special = season_number == 0

                if not is_special:
                    # Store mapping of absolute number to season/episode
                    absolute_mapping[absolute_episode_count] = {
                        "season": season_number,
                        "episode": episode_number,
                        "episode_data": ep
                    }

                episode_data = {
                    "id": ep.get("id"),
                    "name": ep.get("name", ""),
                    "overview": ep.get("overview", ""),
                    "seasonNumber": season_number,
                    "episodeNumber": episode_number,
                    "absoluteNumber": absolute_episode_count if not is_special else None,
                    "aired": ep.get("aired"),
                    "runtime": ep.get("runtime"),
                    "imageUrl": ep.get("image"),
                    "thumbUrl": ep.get("thumbnail"),
                    "isMovie": ep.get("isMovie", False),
                    "airsAfterSeason": ep.get("airsAfterSeason"),
                    "airsBeforeSeason": ep.get("airsBeforeSeason"),
                    "airsBeforeEpisode": ep.get("airsBeforeEpisode"),
                    "productionCode": ep.get("productionCode", ""),
                    "finaleType": ep.get("finaleType", ""),
                    "year": ep.get("year")
                }

                # Create a season entry if it doesn't exist
                if season_number not in episodes_by_season:
                    episodes_by_season[season_number] = []

                # Add the episode to its season
                episodes_by_season[season_number].append(episode_data)

            # Sort episodes within each season by episode number
            for s in episodes_by_season:
                valid_episodes = [ep for ep in episodes_by_season[s] if ep["episodeNumber"] is not None]
                episodes_by_season[s] = sorted(valid_episodes, key=lambda ep: ep["episodeNumber"])

            # If season and episode were provided, try to find the matching episode
            if season is not None and episode is not None:
                found_episode = None

                # Ensure season is an integer
                try:
                    season = int(season)
                except (ValueError, TypeError):
                    if debug:
                        console.print(f"[yellow]Invalid season number provided: {season}, using as-is[/yellow]")

                if debug:
                    console.print(f"[cyan]Looking for season {season} (type: {type(season)}) in episodes_by_season keys: {sorted(episodes_by_season.keys())} (types: {[type(s) for s in episodes_by_season.keys()]})[/cyan]")

                # First try to find the episode in the specified season
                if season in episodes_by_season:
                    if debug:
                        console.print(f"[green]Found season {season} in episodes_by_season[/green]")

                    # Convert episode to int if not already
                    try:
                        episode = int(episode)
                    except (ValueError, TypeError):
                        if debug:
                            console.print(f"[yellow]Invalid episode number provided: {episode}, using as-is[/yellow]")

                    max_episode_in_season = max([ep["episodeNumber"] or 0 for ep in episodes_by_season[season]])

                    if episode <= max_episode_in_season:
                        # Episode exists in this season normally
                        for ep in episodes_by_season[season]:
                            if ep["episodeNumber"] == episode:
                                found_episode = ep
                                if debug:
                                    console.print(f"[green]Found episode S{season}E{episode} directly: {ep['name']}[/green]")
                                # Since we found it directly, return the original season and episode
                                return (season, episode)
                    else:
                        # Episode number is greater than max in this season, so try absolute numbering
                        if debug:
                            console.print(f"[yellow]Episode {episode} is greater than max episode ({max_episode_in_season}) in season {season}[/yellow]")
                            console.print("[yellow]Trying to find by absolute episode number...[/yellow]")

                        # Calculate absolute episode number
                        absolute_number = episode
                        for s in range(1, season):
                            if s in episodes_by_season:
                                absolute_number += len(episodes_by_season[s])

                        if absolute_number in absolute_mapping:
                            actual_season = absolute_mapping[absolute_number]["season"]
                            actual_episode = absolute_mapping[absolute_number]["episode"]

                            # Find the episode in the seasons data
                            for ep in episodes_by_season[actual_season]:
                                if ep["episodeNumber"] == actual_episode:
                                    found_episode = ep
                                    if debug:
                                        console.print(f"[green]Found by absolute number {absolute_number}: S{actual_season}E{actual_episode} - {ep['name']}[/green]")
                                        console.print(f"[bold yellow]Note: S{season}E{episode} maps to S{actual_season}E{actual_episode} using absolute numbering[/bold yellow]")
                                    # Return the absolute-based season and episode since that's what corresponds to the actual content
                                    return (actual_season, actual_episode)
                        else:
                            if debug:
                                console.print(f"[red]Could not find episode with absolute number {absolute_number}[/red]")
                            # Return original values if absolute mapping failed
                            return (season, episode)
                else:
                    if debug:
                        console.print(f"[red]Season {season} not found in series[/red]")
                    # Return original values if season wasn't found
                    return (season, episode)

                # If we get here and haven't returned yet, return the original values
                if not found_episode:
                    if debug:
                        console.print(f"[yellow]No matching episode found, keeping original S{season}E{episode}[/yellow]")
                    return (season, episode)

            # If we get here, no specific episode was requested or processing, so return the original values
            return (season, episode)

    except httpx.HTTPStatusError as e:
        console.print(f"[red]HTTP error occurred: {e.response.status_code} - {e.response.text}[/red]")
        return (season, episode)
    except httpx.RequestError as e:
        console.print(f"[red]Request error occurred: {e}[/red]")
        return (season, episode)
    except Exception as e:
        console.print(f"[red]Error fetching TVDb episode list: {str(e)}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return (season, episode)
