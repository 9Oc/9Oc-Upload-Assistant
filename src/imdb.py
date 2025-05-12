from src.console import console
import json
import httpx
from datetime import datetime


async def get_imdb_aka_api(imdb_id, manual_language=None):
    if imdb_id == 0:
        return "", None
    if not str(imdb_id).startswith("tt"):
        imdb_id = f"tt{imdb_id:07d}"
    query = {
        "query": f"""
            query {{
                title(id: "{imdb_id}") {{
                    id
                    titleText {{
                        text
                        isOriginalTitle
                    }}
                    originalTitleText {{
                        text
                    }}
                    countriesOfOrigin {{
                        countries {{
                            id
                        }}
                    }}
                }}
            }}
        """
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post("https://api.graphql.imdb.com/", json=query, headers={"Content-Type": "application/json"}, timeout=10)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            console.print(f"[red]IMDb API error: {e.response.status_code}[/red]")
            return "", None
        except httpx.RequestError as e:
            console.print(f"[red]IMDb API Network error: {e}[/red]")
            return "", None

    # Check if `data` and `title` exist
    title_data = data.get("data", {}).get("title")
    if title_data is None:
        console.print("Title data is missing from response")
        return "", None

    # Extract relevant fields from the response
    aka_check = title_data.get("originalTitleText", {})
    if aka_check:
        aka = title_data.get("originalTitleText", {}).get("text", "")
    else:
        return "", None
    title_txt_check = title_data.get("titleText", {})
    if title_txt_check:
        is_original = title_data.get("titleText", {}).get("isOriginalTitle", False)
        title_text = title_data.get("titleText", {}).get("text", "")
    else:
        return "", None
    if manual_language:
        original_language = manual_language
    else:
        original_language = None

    if title_text != aka:
        aka = f" AKA {aka}"
    elif is_original and aka:
        aka = f" AKA {aka}"

    return aka, original_language


async def safe_get(data, path, default=None):
    for key in path:
        if isinstance(data, dict):
            data = data.get(key, default)
        else:
            return default
    return data


async def get_imdb_info_api(imdbID, manual_language=None, debug=False):
    imdb_info = {}

    if not imdbID or imdbID == 0:
        imdb_info['type'] = None
        return imdb_info

    try:
        if not str(imdbID).startswith("tt"):
            imdbID = f"tt{imdbID:07d}"
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        return imdb_info

    query = {
        "query": f"""
        query GetTitleInfo {{
            title(id: "{imdbID}") {{
            id
            titleText {{
                text
                isOriginalTitle
                country {{
                    text
                }}
            }}
            originalTitleText {{
                text
            }}
            releaseYear {{
                year
            }}
            titleType {{
                id
            }}
            plot {{
                plotText {{
                plainText
                }}
            }}
            ratingsSummary {{
                aggregateRating
                voteCount
            }}
            primaryImage {{
                url
            }}
            runtime {{
                displayableProperty {{
                value {{
                    plainText
                }}
                }}
                seconds
            }}
            titleGenres {{
                genres {{
                genre {{
                    text
                }}
                }}
            }}
            principalCredits {{
                category {{
                text
                id
                }}
                credits {{
                name {{
                    id
                    nameText {{
                    text
                    }}
                }}
                }}
            }}
            episodes {{
                episodes(first: 500) {{
                edges {{
                    node {{
                    id
                    titleText {{
                        text
                    }}
                    releaseYear {{
                        year
                    }}
                    releaseDate {{
                        year
                        month
                        day
                    }}
                    }}
                }}
                pageInfo {{
                    hasNextPage
                    hasPreviousPage
                }}
                total
                }}
            }}
            akas(first: 100) {{
            edges {{
                node {{
                text
                country {{
                    text
                }}
                language {{
                    text
                }}
                }}
            }}
            }}
            }}
        }}
        """
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post("https://api.graphql.imdb.com/", json=query, headers={"Content-Type": "application/json"}, timeout=10)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            console.print(f"[red]IMDb API error: {e.response.status_code}[/red]")
            return imdb_info
        except httpx.RequestError as e:
            console.print(f"[red]IMDb API Network error: {e}[/red]")
            return imdb_info

    title_data = await safe_get(data, ["data", "title"], {})
    if not title_data:
        return imdb_info  # Return empty if no data found

    imdb_info['imdbID'] = imdbID
    imdb_info['title'] = await safe_get(title_data, ['titleText', 'text'])
    imdb_info['country'] = await safe_get(title_data, ['titleText', 'country', 'text'])
    imdb_info['year'] = await safe_get(title_data, ['releaseYear', 'year'])
    original_title = await safe_get(title_data, ['originalTitleText', 'text'], '')
    imdb_info['aka'] = original_title if original_title and original_title != imdb_info['title'] else imdb_info['title']
    imdb_info['type'] = await safe_get(title_data, ['titleType', 'id'], None)
    runtime_seconds = await safe_get(title_data, ['runtime', 'seconds'], 0)
    imdb_info['runtime'] = str(runtime_seconds // 60 if runtime_seconds else 60)
    imdb_info['cover'] = await safe_get(title_data, ['primaryImage', 'url'])
    imdb_info['plot'] = await safe_get(title_data, ['plot', 'plotText', 'plainText'], 'No plot available')

    genres = await safe_get(title_data, ['titleGenres', 'genres'], [])
    genre_list = [await safe_get(g, ['genre', 'text'], '') for g in genres]
    imdb_info['genres'] = ', '.join(filter(None, genre_list))

    imdb_info['rating'] = await safe_get(title_data, ['ratingsSummary', 'aggregateRating'], 'N/A')

    imdb_info['directors'] = []
    principal_credits = await safe_get(title_data, ['principalCredits'], [])
    if isinstance(principal_credits, list):
        for pc in principal_credits:
            category_text = await safe_get(pc, ['category', 'text'], '')
            if 'Direct' in category_text:
                credits = await safe_get(pc, ['credits'], [])
                for c in credits:
                    name_id = await safe_get(c, ['name', 'id'], '')
                    if name_id.startswith('nm'):
                        imdb_info['directors'].append(name_id)
                break

    akas_edges = await safe_get(title_data, ['akas', 'edges'], default=[])
    imdb_info['akas'] = [
        {
            "title": await safe_get(edge, ['node', 'text']),
            "country": await safe_get(edge, ['node', 'country', 'text']),
            "language": await safe_get(edge, ['node', 'language', 'text']),
        }
        for edge in akas_edges
    ]

    if manual_language:
        imdb_info['original_language'] = manual_language

    imdb_info['episodes'] = []
    episodes_data = await safe_get(title_data, ['episodes', 'episodes'], None)
    if episodes_data:
        edges = await safe_get(episodes_data, ['edges'], [])
        for edge in edges:
            node = await safe_get(edge, ['node'], {})
            episode_info = {
                'id': await safe_get(node, ['id'], ''),
                'title': await safe_get(node, ['titleText', 'text'], 'Unknown Title'),
                'release_year': await safe_get(node, ['releaseYear', 'year'], 'Unknown Year'),
                'release_date': {
                    'year': await safe_get(node, ['releaseDate', 'year'], None),
                    'month': await safe_get(node, ['releaseDate', 'month'], None),
                    'day': await safe_get(node, ['releaseDate', 'day'], None),
                }
            }
            imdb_info['episodes'].append(episode_info)

    episodes = imdb_info.get('episodes', [])
    current_year = datetime.now().year
    release_years = [episode['release_year'] for episode in episodes if 'release_year' in episode and isinstance(episode['release_year'], int)]
    if release_years:
        closest_year = min(release_years, key=lambda year: abs(year - current_year))
        imdb_info['tv_year'] = closest_year
    else:
        imdb_info['tv_year'] = None

    if debug:
        console.print(f"[yellow]IMDb Response: {json.dumps(imdb_info, indent=2)[:600]}...[/yellow]")

    return imdb_info


async def search_imdb(filename, search_year):
    import re
    filename = re.sub(r'\s+[A-Z]{2}$', '', filename.strip())
    console.print(f"[yellow]Searching IMDb (GraphQL) for {filename} and year {search_year}...[/yellow]")
    imdbID = 0
    url = "https://api.graphql.imdb.com/"
    query = {
        "query": f"""
            {{
                advancedTitleSearch(
                    first: 10,
                    constraints: {{ titleTextConstraint: {{ searchTerm: "{filename}" }} }}
                ) {{
                    total
                    edges {{
                        node {{
                            title {{
                                id
                                titleText {{
                                    text
                                }}
                                titleType {{
                                    text
                                }}
                                releaseYear {{
                                    year
                                }}
                                plot {{
                                    plotText {{
                                    plainText
                                    }}
                                }}
                            }}
                        }}
                    }}
                }}
            }}
        """
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=query, headers={"Content-Type": "application/json"}, timeout=10)
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        console.print(f"[red]IMDb GraphQL API error: {e}[/red]")
        return 0

    results = await safe_get(data, ["data", "advancedTitleSearch", "edges"], [])
    console.print(f"[yellow]Found {len(results)} results...[/yellow]")

    for idx, edge in enumerate(results):
        node = await safe_get(edge, ["node"], {})
        title = await safe_get(node, ["title"], {})
        title_text = await safe_get(title, ["titleText", "text"], "")
        year = await safe_get(title, ["releaseYear", "year"], None)
        imdb_id = await safe_get(title, ["id"], "")
        title_type = await safe_get(title, ["titleType", "text"], "")
        plot = await safe_get(title, ["plot", "plotText", "plainText"], "")

        console.print(f"[cyan]Result {idx+1}: {title_text} - ({year}) - {imdb_id} - Type: {title_type}[/cyan]")
        if plot:
            console.print(f"[green]Plot: {plot}[/green]")

    if results:
        console.print("[yellow]Enter the number of the correct entry, or 0 for none:[/yellow]")
        try:
            user_input = input("> ").strip()
            if user_input.isdigit():
                selection = int(user_input)
                if 1 <= selection <= len(results):
                    selected = results[selection - 1]
                    imdb_id = await safe_get(selected, ["node", "title", "id"], "")
                    if imdb_id:
                        imdbID = int(imdb_id.replace('tt', '').strip())
                        return imdbID
                # If 0 or invalid, fall through to return imdbID = 0
        except Exception as e:
            console.print(f"[red]Error reading input: {e}[/red]")

    return imdbID
